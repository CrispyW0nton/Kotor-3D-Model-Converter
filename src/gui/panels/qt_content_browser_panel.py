"""Unified Qt Content Browser for GhostRigger assets."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets

from src.gui.qt_lib.assets.qt_theme import icon
from src.gui.qt_lib.panels.qt_library_panel import enrich_library_rows, infer_model_category


ASSET_TYPES = ("All", "Model", "Animation", "Texture", "Blueprint", "Module", "Scene")


@dataclass(slots=True)
class ContentAssetDescriptor:
    """Small UI descriptor that keeps source data lossless for callers."""

    asset_type: str
    name: str
    game: str = ""
    category: str = ""
    source: str = ""
    row: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    tags: tuple[str, ...] = ()

    @property
    def searchable_text(self) -> str:
        values = [
            self.asset_type,
            self.name,
            self.game,
            self.category,
            self.source,
            *self.tags,
            *(str(value) for value in self.metadata.values()),
        ]
        return " ".join(value for value in values if value).lower()


def descriptor_from_library_row(row: dict) -> ContentAssetDescriptor:
    item = dict(row)
    category = str(item.get("category") or infer_model_category(str(item.get("resref", ""))))
    asset_type = "Module" if category == "Module" else "Blueprint" if category == "Template" else "Model"
    source = str(item.get("source", ""))
    name = str(item.get("resref", ""))
    return ContentAssetDescriptor(
        asset_type=asset_type,
        name=name,
        game=str(item.get("game", "")),
        category=category,
        source=source,
        row=item,
        metadata={
            "area": item.get("area_label") or item.get("area_name") or "",
            "module": item.get("module_code") or "",
            "class": item.get("model_class") or "",
        },
        tags=tuple(str(value) for value in (category, item.get("location", "")) if value),
    )


def descriptor_from_animation_entry(entry: dict) -> ContentAssetDescriptor:
    item = dict(entry)
    model = str(item.get("model") or item.get("model_name") or "")
    anim = str(item.get("animation") or item.get("anim_name") or "")
    game = str(item.get("game", ""))
    source = str(item.get("source", ""))
    object_name = str(item.get("object_name", ""))
    resref = str(item.get("resref", ""))
    return ContentAssetDescriptor(
        asset_type="Animation",
        name=anim or model,
        game=game,
        category="Animation",
        source=source,
        row=item,
        metadata={
            "model": model,
            "object": object_name,
            "resref": resref,
            "frames": item.get("frames", ""),
            "length": item.get("length", ""),
            "source": source,
        },
        tags=tuple(str(value) for value in ("animation", model, object_name, resref, source) if value),
    )


class QtContentAssetItem(QtWidgets.QTreeWidgetItem):
    def __init__(self, asset: ContentAssetDescriptor):
        model_or_meta = str(asset.metadata.get("model") or asset.metadata.get("area") or asset.category or "")
        has_path_separator = bool(asset.source) and ("\\" in asset.source or "/" in asset.source)
        source_name = Path(asset.source).name if has_path_separator else asset.source
        super().__init__([
            asset.name,
            asset.asset_type,
            asset.game,
            source_name,
            asset.category,
            model_or_meta,
        ])
        self.asset = asset
        self.setData(0, QtCore.Qt.UserRole, asset)


class QtContentBrowserPanel(QtWidgets.QWidget):
    """Unreal-style browser that owns models, animations, and future asset rows."""

    loadRequested = QtCore.Signal(str, str)
    extractRequested = QtCore.Signal(dict)
    retargetSourceRequested = QtCore.Signal(dict)
    retargetTargetRequested = QtCore.Signal(dict)
    levelEditorImportRequested = QtCore.Signal(dict)
    batchRequested = QtCore.Signal(str, list)
    scanRequested = QtCore.Signal()
    deepScanRequested = QtCore.Signal()
    libraryActionRequested = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setObjectName("contentBrowser")
        self._library_rows: list[dict] = []
        self._scene_animation_entries: list[dict] = []
        self._scanned_animation_entries: list[dict] = []
        self._assets: list[ContentAssetDescriptor] = []
        self._active_nav: tuple[str, str] = ("type", "All")
        self._splitter_user_adjusted = False
        self._splitter_layout_applied = False
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(5)

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setOpaqueResize(True)
        self.splitter.splitterMoved.connect(self._on_splitter_moved)
        root.addWidget(self.splitter, 1)

        self.nav_tree = QtWidgets.QTreeWidget()
        self.nav_tree.setHeaderHidden(True)
        self.nav_tree.setObjectName("contentBrowserNavigation")
        self.nav_tree.setMinimumWidth(96)
        self.nav_tree.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        self.nav_tree.itemSelectionChanged.connect(self._on_navigation_changed)

        self.details = QtWidgets.QWidget()
        self.details.setObjectName("contentBrowserDetails")
        self.details.setMinimumWidth(112)
        self.details.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        details_layout = QtWidgets.QVBoxLayout(self.details)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(5)
        self.detail_title = QtWidgets.QLabel("Select an asset")
        self.detail_title.setProperty("heading", True)
        self.detail_text = QtWidgets.QPlainTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMaximumBlockCount(80)
        details_layout.addWidget(self.detail_title)
        details_layout.addWidget(self.detail_text, 1)
        self._build_action_buttons(details_layout)

        self.sidebar = QtWidgets.QWidget()
        self.sidebar.setObjectName("contentBrowserSidebar")
        self.sidebar.setMinimumWidth(126)
        self.sidebar.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        sidebar_layout = QtWidgets.QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(5)
        sidebar_layout.addWidget(self.nav_tree, 2)
        sidebar_layout.addWidget(self.details, 3)
        self.splitter.addWidget(self.sidebar)

        center = QtWidgets.QWidget()
        self.asset_area = center
        center.setMinimumWidth(180)
        center.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        center_layout = QtWidgets.QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(5)
        self._build_filters(center_layout)
        self.asset_view = QtWidgets.QTreeWidget()
        self.asset_view.setObjectName("contentBrowserAssets")
        self.asset_view.setHeaderLabels(["Name", "Type", "Game", "Source", "Category", "Meta"])
        self.asset_view.setSortingEnabled(True)
        self.asset_view.setRootIsDecorated(False)
        self.asset_view.setAlternatingRowColors(True)
        self.asset_view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.asset_view.setDragEnabled(True)
        self.asset_view.itemDoubleClicked.connect(lambda _item, _column: self._activate_selected())
        self.asset_view.itemSelectionChanged.connect(self._update_details)
        self.asset_view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.asset_view.customContextMenuRequested.connect(self._show_context_menu)
        center_layout.addWidget(self.asset_view, 1)
        self.count_label = QtWidgets.QLabel("")
        center_layout.addWidget(self.count_label)
        self.splitter.addWidget(center)

        status_row = QtWidgets.QHBoxLayout()
        self.status_label = QtWidgets.QLabel("No game directory set")
        status_row.addWidget(self.status_label, 1)
        self.scan_anims_button = QtWidgets.QPushButton("Scan Animations")
        self.scan_anims_button.setProperty("compact", True)
        self.scan_anims_button.clicked.connect(lambda: self.libraryActionRequested.emit("Scan Animations"))
        status_row.addWidget(self.scan_anims_button)
        self.refresh_anims_button = QtWidgets.QPushButton("Refresh Animations")
        self.refresh_anims_button.setProperty("compact", True)
        self.refresh_anims_button.clicked.connect(lambda: self.libraryActionRequested.emit("Refresh"))
        status_row.addWidget(self.refresh_anims_button)
        for label, fmt in (("Batch OBJ", "obj"), ("Batch ASCII", "ascii"), ("Batch TGA", "tga")):
            button = QtWidgets.QPushButton(label)
            button.setProperty("compact", True)
            button.clicked.connect(lambda _checked=False, f=fmt: self.batchRequested.emit(f, self.visible_rows()))
            status_row.addWidget(button)
        self.deep_button = QtWidgets.QPushButton("Deep Scan")
        self.scan_button = QtWidgets.QPushButton("Scan")
        self.scan_button.setProperty("accent", True)
        self.deep_button.setProperty("compact", True)
        self.scan_button.setProperty("compact", True)
        self.deep_button.clicked.connect(self.deepScanRequested.emit)
        self.scan_button.clicked.connect(self.scanRequested.emit)
        status_row.addWidget(self.deep_button)
        status_row.addWidget(self.scan_button)
        root.addLayout(status_row)

        self._rebuild_navigation()
        self._apply_filter()
        QtCore.QTimer.singleShot(0, self._apply_initial_splitter_sizes)

    def _build_filters(self, layout: QtWidgets.QVBoxLayout) -> None:
        search_row = QtWidgets.QHBoxLayout()
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search assets")
        self.search_edit.textChanged.connect(self._apply_filter)
        clear = QtWidgets.QPushButton("x")
        clear.setProperty("compact", True)
        clear.clicked.connect(self.search_edit.clear)
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(clear)
        layout.addLayout(search_row)

        filters = QtWidgets.QHBoxLayout()
        self.type_filter = QtWidgets.QComboBox()
        self.type_filter.addItems(ASSET_TYPES)
        self.type_filter.currentTextChanged.connect(self._apply_filter)
        self.game_filter = QtWidgets.QComboBox()
        self.game_filter.addItems(["All", "K1", "K2"])
        self.game_filter.currentTextChanged.connect(self._apply_filter)
        self.source_filter = QtWidgets.QComboBox()
        self.source_filter.addItem("All Sources")
        self.source_filter.currentTextChanged.connect(self._apply_filter)
        self.tag_filter = QtWidgets.QComboBox()
        self.tag_filter.addItems(["All Tags", "Characters", "Modules", "Templates", "Current Model"])
        self.tag_filter.currentTextChanged.connect(self._apply_filter)
        self.recency_filter = QtWidgets.QComboBox()
        self.recency_filter.addItems(["Any Time", "Recent First"])
        self.recency_filter.currentTextChanged.connect(self._apply_filter)
        self.compat_filter = QtWidgets.QComboBox()
        self.compat_filter.addItems(["All Compatibility", "Current Game", "Cross-Game"])
        self.compat_filter.currentTextChanged.connect(self._apply_filter)
        for label, combo in (
            ("Asset Type", self.type_filter),
            ("Game", self.game_filter),
            ("Source", self.source_filter),
            ("Tags", self.tag_filter),
            ("Updated", self.recency_filter),
            ("Compatibility", self.compat_filter),
        ):
            filters.addLayout(self._labeled_filter(label, combo))
        layout.addLayout(filters)

    def _labeled_filter(self, text: str, combo: QtWidgets.QComboBox) -> QtWidgets.QVBoxLayout:
        wrapper = QtWidgets.QVBoxLayout()
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.setSpacing(2)
        label = QtWidgets.QLabel(text)
        label.setBuddy(combo)
        combo.setAccessibleName(text)
        wrapper.addWidget(label)
        wrapper.addWidget(combo)
        return wrapper

    def _build_action_buttons(self, layout: QtWidgets.QVBoxLayout) -> None:
        self.primary_button = self._compact_action_button("Open")
        self.primary_button.setProperty("accent", True)
        self.primary_button.clicked.connect(self._activate_selected)
        layout.addWidget(self.primary_button)

        grid = QtWidgets.QGridLayout()
        self.preview_button = self._compact_action_button("Preview")
        self.stop_button = self._compact_action_button("Stop")
        self.apply_button = self._compact_action_button("Apply Animation")
        self.extract_button = self._compact_action_button("Extract")
        self.level_button = self._compact_action_button("Add to Scene")
        self.inspect_button = self._compact_action_button("Inspect")
        self.export_button = self._compact_action_button("Export")
        self.source_button = self._compact_action_button("Retarget Source")
        self.target_button = self._compact_action_button("Retarget Target")
        buttons = [
            self.preview_button,
            self.stop_button,
            self.apply_button,
            self.extract_button,
            self.level_button,
            self.inspect_button,
            self.export_button,
            self.source_button,
            self.target_button,
        ]
        for index, button in enumerate(buttons):
            button.setProperty("compact", True)
            grid.addWidget(button, index // 2, index % 2)
        self.preview_button.clicked.connect(lambda: self.libraryActionRequested.emit("Preview"))
        self.stop_button.clicked.connect(lambda: self.libraryActionRequested.emit("Stop"))
        self.apply_button.clicked.connect(lambda: self.libraryActionRequested.emit("Load"))
        self.extract_button.clicked.connect(self.extract_selected)
        self.level_button.clicked.connect(self.import_selected_to_level)
        self.inspect_button.clicked.connect(lambda: self.libraryActionRequested.emit("Inspect"))
        self.export_button.clicked.connect(lambda: self.libraryActionRequested.emit("Export"))
        self.source_button.clicked.connect(lambda: self._emit_retarget("source"))
        self.target_button.clicked.connect(lambda: self._emit_retarget("target"))
        layout.addLayout(grid)

    def _compact_action_button(self, text: str) -> QtWidgets.QPushButton:
        button = QtWidgets.QPushButton(text)
        button.setProperty("compact", True)
        button.setProperty("_gr_full_text", text)
        button.setToolTip(text)
        button.setMinimumWidth(0)
        button.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        return button

    def set_rows(self, rows: list[dict]) -> None:
        self._library_rows = enrich_library_rows(rows)
        self._rebuild_assets()

    def set_animation_entries(self, entries: list[dict]) -> None:
        self.set_scene_animation_entries(entries)

    def set_scene_animation_entries(self, entries: list[dict]) -> None:
        self._scene_animation_entries = [dict(entry) for entry in entries]
        self._rebuild_assets()

    def set_scanned_animation_entries(self, entries: list[dict]) -> None:
        self._scanned_animation_entries = [dict(entry) for entry in entries]
        self._rebuild_assets()

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def selected_asset(self) -> Optional[ContentAssetDescriptor]:
        item = self.asset_view.currentItem()
        return getattr(item, "asset", None) if item else None

    def selected_row(self) -> Optional[dict]:
        asset = self.selected_asset()
        if asset is None or asset.asset_type == "Animation":
            return None
        return dict(asset.row)

    def selected_entry(self) -> Optional[dict]:
        asset = self.selected_asset()
        if asset is None or asset.asset_type != "Animation":
            return None
        return dict(asset.row)

    def visible_assets(self) -> list[ContentAssetDescriptor]:
        assets = []
        for index in range(self.asset_view.topLevelItemCount()):
            asset = getattr(self.asset_view.topLevelItem(index), "asset", None)
            if asset is not None:
                assets.append(asset)
        return assets

    def visible_rows(self) -> list[dict]:
        rows = []
        for asset in self.visible_assets():
            if asset.asset_type != "Animation" and asset.row.get("resref"):
                rows.append(dict(asset.row))
        return rows

    def select_asset_type(self, asset_type: str) -> None:
        text = asset_type if asset_type in ASSET_TYPES else "All"
        self.type_filter.setCurrentText(text)
        self._select_navigation("type", text)

    def load_selected(self) -> None:
        row = self.selected_row()
        if row:
            self.loadRequested.emit(str(row.get("resref", "")), str(row.get("game", "")))

    def extract_selected(self) -> None:
        row = self.selected_row()
        if row:
            self.extractRequested.emit(row)

    def import_selected_to_level(self) -> None:
        row = self.selected_row()
        if row:
            self.levelEditorImportRequested.emit(row)

    def apply_ghost_theme(self, theme) -> None:
        return None

    def apply_ghost_layout(self, layout) -> None:
        panel = layout.panel("contentBrowser")
        self.setMinimumWidth(panel.min_width)
        spacing = layout.spacing_value("panelSpacing", 5)
        for widget in (self, self.sidebar, self.details):
            widget_layout = widget.layout()
            if widget_layout is not None:
                widget_layout.setSpacing(spacing)
        self.splitter.setHandleWidth(layout.spacing_value("splitterHandleWidth", 6))
        if not self._splitter_user_adjusted and not self._splitter_layout_applied:
            self._apply_initial_splitter_sizes()

    def _on_splitter_moved(self, _pos: int, _index: int) -> None:
        self._splitter_user_adjusted = True

    def _apply_initial_splitter_sizes(self) -> None:
        if self._splitter_user_adjusted or self._splitter_layout_applied:
            return
        width = max(1, self.splitter.width())
        if width < 120:
            return
        sidebar = max(180, min(320, int(width * 0.26)))
        center = max(180, width - sidebar)
        self.splitter.setSizes([sidebar, center])
        self._splitter_layout_applied = True

    def _rebuild_assets(self) -> None:
        self._assets = [
            *(descriptor_from_library_row(row) for row in self._library_rows),
            *(descriptor_from_animation_entry(entry) for entry in self._scene_animation_entries),
            *(descriptor_from_animation_entry(entry) for entry in self._scanned_animation_entries),
        ]
        self._rebuild_sources()
        self._rebuild_navigation()
        self._apply_filter()

    def _rebuild_sources(self) -> None:
        current = self.source_filter.currentText() if hasattr(self, "source_filter") else "All Sources"
        self.source_filter.blockSignals(True)
        self.source_filter.clear()
        self.source_filter.addItem("All Sources")
        sources = sorted({asset.source for asset in self._assets if asset.source})
        self.source_filter.addItems(sources)
        index = self.source_filter.findText(current)
        self.source_filter.setCurrentIndex(index if index >= 0 else 0)
        self.source_filter.blockSignals(False)

    def _rebuild_navigation(self) -> None:
        self.nav_tree.blockSignals(True)
        self.nav_tree.clear()
        all_item = QtWidgets.QTreeWidgetItem(["All Assets"])
        all_item.setData(0, QtCore.Qt.UserRole, ("type", "All"))
        self.nav_tree.addTopLevelItem(all_item)
        for asset_type in ASSET_TYPES[1:]:
            item = QtWidgets.QTreeWidgetItem([asset_type])
            item.setData(0, QtCore.Qt.UserRole, ("type", asset_type))
            self.nav_tree.addTopLevelItem(item)
        categories = sorted({asset.category for asset in self._assets if asset.category})
        if categories:
            folders = QtWidgets.QTreeWidgetItem(["Folders / Categories"])
            folders.setData(0, QtCore.Qt.UserRole, ("type", "All"))
            self.nav_tree.addTopLevelItem(folders)
            for category in categories:
                child = QtWidgets.QTreeWidgetItem([category])
                child.setData(0, QtCore.Qt.UserRole, ("category", category))
                folders.addChild(child)
            folders.setExpanded(True)
        self.nav_tree.expandAll()
        self.nav_tree.blockSignals(False)
        self._select_navigation(*self._active_nav)

    def _select_navigation(self, key: str, value: str) -> None:
        target = (key, value)
        for item in self._walk_nav_items():
            if item.data(0, QtCore.Qt.UserRole) == target:
                self.nav_tree.setCurrentItem(item)
                return

    def _walk_nav_items(self):
        for index in range(self.nav_tree.topLevelItemCount()):
            root = self.nav_tree.topLevelItem(index)
            yield root
            for child_index in range(root.childCount()):
                yield root.child(child_index)

    def _on_navigation_changed(self) -> None:
        item = self.nav_tree.currentItem()
        data = item.data(0, QtCore.Qt.UserRole) if item is not None else ("type", "All")
        if not isinstance(data, tuple) or len(data) != 2:
            data = ("type", "All")
        self._active_nav = (str(data[0]), str(data[1]))
        if self._active_nav[0] == "type":
            self.type_filter.blockSignals(True)
            self.type_filter.setCurrentText(self._active_nav[1] if self._active_nav[1] in ASSET_TYPES else "All")
            self.type_filter.blockSignals(False)
        self._apply_filter()

    def _apply_filter(self) -> None:
        if not hasattr(self, "asset_view"):
            return
        needle = self.search_edit.text().strip().lower()
        asset_type = self.type_filter.currentText()
        game = self.game_filter.currentText()
        source = self.source_filter.currentText()
        tag = self.tag_filter.currentText()
        compatibility = self.compat_filter.currentText()
        nav_key, nav_value = self._active_nav

        self.asset_view.clear()
        for asset in self._assets:
            if asset_type != "All" and asset.asset_type != asset_type:
                continue
            if game != "All" and asset.game != game:
                continue
            if source != "All Sources" and asset.source != source:
                continue
            if nav_key == "category" and asset.category != nav_value:
                continue
            if tag != "All Tags" and not self._matches_tag(asset, tag):
                continue
            if compatibility == "Current Game" and game != "All" and asset.game and asset.game != game:
                continue
            if compatibility == "Cross-Game" and asset.game not in {"", "K1", "K2"}:
                continue
            if needle and needle not in asset.searchable_text:
                continue
            item = QtContentAssetItem(asset)
            item.setIcon(0, self._asset_icon(asset))
            self.asset_view.addTopLevelItem(item)
        self.count_label.setText(f"{self.asset_view.topLevelItemCount()} asset(s) shown")
        for column in range(self.asset_view.columnCount()):
            self.asset_view.resizeColumnToContents(column)
        self._update_details()

    def _matches_tag(self, asset: ContentAssetDescriptor, tag: str) -> bool:
        haystack = " ".join([asset.category, asset.source, *asset.tags]).lower()
        mapping = {
            "Characters": "character",
            "Modules": "module",
            "Templates": "template",
            "Current Model": "current model",
        }
        return mapping.get(tag, tag).lower() in haystack

    def _asset_icon(self, asset: ContentAssetDescriptor):
        if asset.asset_type == "Animation":
            return icon("anims", 16)
        if asset.asset_type == "Module":
            return icon("cat_module", 16)
        if asset.asset_type == "Blueprint":
            return icon("skeleton", 16)
        if asset.category == "Creature":
            return icon("cat_creature", 16)
        if asset.category == "Character":
            return icon("cat_character", 16)
        if asset.category == "Item/Armor/Weapons":
            return icon("cat_item", 16)
        return icon("library", 16)

    def _update_details(self) -> None:
        asset = self.selected_asset()
        if asset is None:
            self.detail_title.setText("Select an asset")
            self.detail_text.setPlainText("")
            self._set_action_state(None)
            return
        self.detail_title.setText(asset.name)
        lines = [
            f"Type: {asset.asset_type}",
            f"Game: {asset.game or 'Any'}",
            f"Category: {asset.category or 'Uncategorized'}",
        ]
        if asset.source:
            lines.append(f"Source: {asset.source}")
        for key, value in asset.metadata.items():
            if value not in ("", None):
                lines.append(f"{key.title()}: {value}")
        self.detail_text.setPlainText("\n".join(lines))
        self._set_action_state(asset)

    def _set_action_state(self, asset: Optional[ContentAssetDescriptor]) -> None:
        is_animation = asset is not None and asset.asset_type == "Animation"
        has_model_row = asset is not None and asset.asset_type != "Animation" and bool(asset.row.get("resref"))
        self.primary_button.setText("Preview" if is_animation else "Open")
        self.primary_button.setEnabled(asset is not None)
        self.preview_button.setEnabled(is_animation)
        self.stop_button.setEnabled(True)
        self.apply_button.setEnabled(is_animation)
        self.export_button.setEnabled(is_animation)
        self.inspect_button.setEnabled(asset is not None)
        for button in (self.extract_button, self.level_button, self.source_button, self.target_button):
            button.setEnabled(has_model_row)

    def _activate_selected(self) -> None:
        asset = self.selected_asset()
        if asset is None:
            return
        if asset.asset_type == "Animation":
            self.libraryActionRequested.emit("Preview")
            return
        row = asset.row
        if row.get("resref"):
            self.loadRequested.emit(str(row.get("resref", "")), str(row.get("game", "")))

    def _show_context_menu(self, pos: QtCore.QPoint) -> None:
        item = self.asset_view.itemAt(pos)
        if item is not None:
            self.asset_view.setCurrentItem(item)
        asset = self.selected_asset()
        if asset is None:
            return
        menu = QtWidgets.QMenu(self)
        if asset.asset_type == "Animation":
            preview_action = menu.addAction("Preview Animation")
            stop_action = menu.addAction("Stop Preview")
            load_action = menu.addAction("Load in Current Animations")
            export_action = menu.addAction("Export Animation")
            chosen = menu.exec(self.asset_view.mapToGlobal(pos))
            if chosen is preview_action:
                self.libraryActionRequested.emit("Preview")
            elif chosen is stop_action:
                self.libraryActionRequested.emit("Stop")
            elif chosen is load_action:
                self.libraryActionRequested.emit("Load")
            elif chosen is export_action:
                self.libraryActionRequested.emit("Export")
            return
        load_action = menu.addAction("Open Model")
        add_to_level_action = menu.addAction("Add to Scene / Level Editor")
        extract_action = menu.addAction("Extract")
        menu.addSeparator()
        source_action = menu.addAction("Send to Retarget Workbench (Source)")
        target_action = menu.addAction("Send to Retarget Workbench (Target)")
        chosen = menu.exec(self.asset_view.mapToGlobal(pos))
        if chosen is load_action:
            self.load_selected()
        elif chosen is add_to_level_action:
            self.import_selected_to_level()
        elif chosen is extract_action:
            self.extract_selected()
        elif chosen is source_action:
            self._emit_retarget("source")
        elif chosen is target_action:
            self._emit_retarget("target")

    def _emit_retarget(self, role: str) -> None:
        row = self.selected_row()
        if not row:
            return
        if role == "source":
            self.retargetSourceRequested.emit(row)
        else:
            self.retargetTargetRequested.emit(row)
