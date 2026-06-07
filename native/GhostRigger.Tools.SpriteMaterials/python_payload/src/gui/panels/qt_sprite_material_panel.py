"""Dockable controls for alpha-card and sprite-like mesh materials."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.gui.qt_lib.assets.qt_theme import heading
from src.gui.qt_lib.panels.qt_skeleton_panel import node_browser_role


class _SpriteMaterialDelegate(QtWidgets.QStyledItemDelegate):
    def sizeHint(self, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex) -> QtCore.QSize:  # noqa: N802
        size = super().sizeHint(option, index)
        size.setHeight(max(size.height(), option.fontMetrics.height() + 8, 24))
        return size


class QtSpriteMaterialPanel(QtWidgets.QWidget):
    spriteSelected = QtCore.Signal(object)
    spriteRenderChanged = QtCore.Signal(list)

    _COLUMNS = ("Visible", "Mesh", "Texture", "Class", "Mode", "Cutoff", "Opacity", "Flags")
    _ORIGINAL_ATTRS = (
        "txi_blending",
        "txi_alpha_test",
        "txi_wateralpha",
        "txi_decal",
        "transparency_hint",
        "alpha",
        "_gr_sprite_render_mode",
        "_gr_sprite_alpha_source",
        "_gr_sprite_glow",
    )
    _CATEGORY_PRESETS = {
        "hilt": {"mode": "opaque", "cutoff": 0.5, "opacity": 1.0, "decal": False, "alpha_source": "", "glow": 0.0},
        "fur_hair": {"mode": "cutout", "cutoff": 0.5, "opacity": 1.0, "decal": False, "alpha_source": "", "glow": 0.0},
        "foliage": {"mode": "cutout", "cutoff": 0.5, "opacity": 1.0, "decal": False, "alpha_source": "", "glow": 0.0},
        "glass_window": {"mode": "blend", "cutoff": 0.5, "opacity": 0.55, "decal": False, "alpha_source": "", "glow": 0.0},
        "glow_blade": {"mode": "lighten", "cutoff": 0.5, "opacity": 1.0, "decal": False, "alpha_source": "luminance", "glow": 1.6},
        "decal": {"mode": "blend", "cutoff": 0.5, "opacity": 1.0, "decal": True, "alpha_source": "", "glow": 0.0},
        "sprite": {"mode": "cutout", "cutoff": 0.5, "opacity": 1.0, "decal": False, "alpha_source": "", "glow": 0.0},
    }

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._model = None
        self._items: dict[QtWidgets.QTreeWidgetItem, object] = {}
        self._updating = False
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(7)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(heading("Sprite Materials"))
        self.count_label = QtWidgets.QLabel("")
        self.count_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        header.addWidget(self.count_label, 1)
        root.addLayout(header)

        self.filter_edit = QtWidgets.QLineEdit()
        self.filter_edit.setPlaceholderText("Filter sprite meshes")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(self._filter_rows)
        root.addWidget(self.filter_edit)

        filter_row = QtWidgets.QHBoxLayout()
        filter_row.setSpacing(8)
        self.candidates_only_check = QtWidgets.QCheckBox("Sprite candidates")
        self.candidates_only_check.setChecked(True)
        self.candidates_only_check.toggled.connect(lambda _state=False: self.refresh())
        self.show_hidden_check = QtWidgets.QCheckBox("Show hidden")
        self.show_hidden_check.setChecked(True)
        self.show_hidden_check.toggled.connect(lambda _state=False: self.refresh())
        filter_row.addWidget(self.candidates_only_check)
        filter_row.addWidget(self.show_hidden_check)
        filter_row.addStretch(1)
        root.addLayout(filter_row)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(len(self._COLUMNS))
        self.tree.setHeaderLabels(list(self._COLUMNS))
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.tree.setItemDelegate(_SpriteMaterialDelegate(self.tree))
        self.tree.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.tree.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.tree.setTextElideMode(QtCore.Qt.ElideMiddle)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemDoubleClicked.connect(lambda item, _column=0: self.spriteSelected.emit(item.data(0, QtCore.Qt.UserRole)))
        header_view = self.tree.header()
        header_view.setStretchLastSection(False)
        header_view.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        for column in range(2, len(self._COLUMNS)):
            header_view.setSectionResizeMode(column, QtWidgets.QHeaderView.ResizeToContents)
        root.addWidget(self.tree, 1)

        editor = QtWidgets.QGroupBox("Selected Sprite")
        form = QtWidgets.QFormLayout(editor)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(6)

        self.visible_check = QtWidgets.QCheckBox("Visible")
        self.visible_check.toggled.connect(lambda _state=False: self._apply_editor())
        form.addRow("", self.visible_check)

        self.category_combo = QtWidgets.QComboBox()
        for label, value in (
            ("Auto", ""),
            ("Hilt", "hilt"),
            ("Fur / Hair", "fur_hair"),
            ("Foliage", "foliage"),
            ("Glass / Window", "glass_window"),
            ("Glow / Blade", "glow_blade"),
            ("Decal", "decal"),
            ("Other Sprite", "sprite"),
        ):
            self.category_combo.addItem(label, value)
        self.category_combo.currentIndexChanged.connect(lambda _index=0: self._apply_editor(apply_category_preset=True))
        form.addRow("Class", self.category_combo)

        self.mode_combo = QtWidgets.QComboBox()
        for label, value in (
            ("Auto / Original", "auto"),
            ("Opaque", "opaque"),
            ("Cutout", "cutout"),
            ("Blend", "blend"),
            ("Additive", "additive"),
            ("Lighten", "lighten"),
        ):
            self.mode_combo.addItem(label, value)
        self.mode_combo.currentIndexChanged.connect(lambda _index=0: self._apply_editor())
        form.addRow("Render Mode", self.mode_combo)

        self.cutoff_spin = QtWidgets.QDoubleSpinBox()
        self.cutoff_spin.setRange(0.0, 1.0)
        self.cutoff_spin.setDecimals(3)
        self.cutoff_spin.setSingleStep(0.025)
        self.cutoff_spin.valueChanged.connect(lambda _value=0.0: self._apply_editor())
        form.addRow("Alpha Cutoff", self.cutoff_spin)

        self.opacity_spin = QtWidgets.QDoubleSpinBox()
        self.opacity_spin.setRange(0.0, 1.0)
        self.opacity_spin.setDecimals(3)
        self.opacity_spin.setSingleStep(0.05)
        self.opacity_spin.valueChanged.connect(lambda _value=0.0: self._apply_editor())
        form.addRow("Opacity", self.opacity_spin)

        self.decal_check = QtWidgets.QCheckBox("Decal surface")
        self.decal_check.toggled.connect(lambda _state=False: self._apply_editor())
        form.addRow("", self.decal_check)
        self.key_matte_check = QtWidgets.QCheckBox("Key black matte")
        self.key_matte_check.toggled.connect(lambda _state=False: self._apply_editor())
        form.addRow("", self.key_matte_check)
        self.glow_spin = QtWidgets.QDoubleSpinBox()
        self.glow_spin.setRange(0.0, 4.0)
        self.glow_spin.setDecimals(2)
        self.glow_spin.setSingleStep(0.1)
        self.glow_spin.valueChanged.connect(lambda _value=0.0: self._apply_editor())
        form.addRow("Glow Boost", self.glow_spin)
        root.addWidget(editor)

        actions = QtWidgets.QGridLayout()
        actions.setHorizontalSpacing(5)
        actions.setVerticalSpacing(5)
        buttons = (
            ("Select", self._select_current),
            ("Hide", lambda: self._set_selected_hidden(True)),
            ("Unhide", lambda: self._set_selected_hidden(False)),
            ("Isolate", self._isolate_selected),
            ("Reset Selected", self._reset_selected),
            ("Reset All", self._reset_all),
        )
        for index, (label, callback) in enumerate(buttons):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(callback)
            actions.addWidget(button, index // 2, index % 2)
        root.addLayout(actions)
        self._set_editor_enabled(False)

    def apply_ghost_theme(self, theme) -> None:
        self.count_label.setStyleSheet(f"color:{theme.color('text.secondary', theme.color('panel.text'))}; font-size:8pt;")
        self.tree.setAlternatingRowColors(True)

    def apply_ghost_layout(self, layout) -> None:
        margin = layout.spacing_value("margin", 4)
        spacing = layout.spacing_value("panelSpacing", 4)
        if self.layout() is not None:
            self.layout().setContentsMargins(margin, margin, margin, margin)
            self.layout().setSpacing(spacing)
        row_height = layout.spacing_value("treeRowHeight", 22)
        self.tree.setUniformRowHeights(True)
        self.tree.setStyleSheet(self.tree.styleSheet() + f" QTreeView::item {{ min-height:{row_height}px; }}")

    def set_model(self, model) -> None:
        self._model = model
        self.refresh()

    def refresh(self) -> None:
        selected_ids = {id(node) for node in self.selected_sprites()}
        self._updating = True
        try:
            self.tree.clear()
            self._items.clear()
            nodes = self._mesh_nodes()
            shown = 0
            for node in nodes:
                if not self.show_hidden_check.isChecked() and bool(getattr(node, "_gr_hidden", False)):
                    continue
                if self.candidates_only_check.isChecked() and not self._is_sprite_candidate(node):
                    continue
                item = self._make_item(node)
                self.tree.addTopLevelItem(item)
                self._items[item] = node
                if id(node) in selected_ids:
                    item.setSelected(True)
                shown += 1
            total_candidates = sum(1 for node in nodes if self._is_sprite_candidate(node))
            self.count_label.setText(f"{shown} shown  {total_candidates} candidates")
            self._filter_rows(self.filter_edit.text())
            self._resize_columns()
        finally:
            self._updating = False
        self._sync_editor_from_selection()

    def selected_sprites(self) -> list:
        return [self._items[item] for item in self.tree.selectedItems() if item in self._items]

    def select_sprite(self, node, *, emit: bool = False) -> bool:
        if node is None:
            return False
        self._updating = not emit
        try:
            self.tree.clearSelection()
            for item, candidate in self._items.items():
                if candidate is node:
                    item.setSelected(True)
                    self.tree.setCurrentItem(item)
                    self.tree.scrollToItem(item)
                    return True
        finally:
            self._updating = False
        return False

    def _mesh_nodes(self) -> list:
        model = self._model
        if model is None:
            return []
        sources = []
        if hasattr(model, "mesh_nodes"):
            sources.append(model.mesh_nodes() or [])
        if hasattr(model, "all_nodes"):
            sources.append(model.all_nodes() or [])
        sources.append(getattr(model, "_gr_extra_module_mesh_nodes", []) or [])
        result = []
        seen: set[int] = set()
        for source in sources:
            for node in source:
                if (
                    node is None
                    or id(node) in seen
                    or not getattr(node, "is_mesh", False)
                    or bool(getattr(node, "is_saber", False))
                    or not self._has_valid_texture(node)
                    or self._node_role(node) not in {"Mesh", "Skin"}
                ):
                    continue
                seen.add(id(node))
                result.append(node)
        return result

    def _make_item(self, node) -> QtWidgets.QTreeWidgetItem:
        item = QtWidgets.QTreeWidgetItem([
            "",
            str(getattr(node, "name", "") or "(unnamed)"),
            self._texture_name(node),
            self._category_label(node),
            self._mode_label(self._render_mode(node)),
            f"{self._alpha_cutoff(node):.3f}",
            f"{self._opacity(node):.3f}",
            self._flag_label(node),
        ])
        item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
        item.setCheckState(0, QtCore.Qt.Unchecked if bool(getattr(node, "_gr_hidden", False)) else QtCore.Qt.Checked)
        item.setIcon(1, self._sprite_icon(node))
        item.setData(0, QtCore.Qt.UserRole, node)
        for column in (5, 6):
            item.setTextAlignment(column, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        item.setToolTip(1, self._tooltip(node))
        return item

    def _on_selection_changed(self) -> None:
        if self._updating:
            return
        self._sync_editor_from_selection()
        selected = self.selected_sprites()
        if selected:
            self.spriteSelected.emit(selected[-1])

    def _on_item_changed(self, item: QtWidgets.QTreeWidgetItem, column: int) -> None:
        if self._updating or column != 0 or item not in self._items:
            return
        node = self._items[item]
        hidden = item.checkState(0) != QtCore.Qt.Checked
        if bool(getattr(node, "_gr_hidden", False)) == hidden:
            return
        setattr(node, "_gr_hidden", hidden)
        self._bump_revision(node)
        self._emit_changed([node])

    def _sync_editor_from_selection(self) -> None:
        selected = self.selected_sprites()
        node = selected[-1] if len(selected) == 1 else None
        self._updating = True
        try:
            self._set_editor_enabled(node is not None)
            if node is None:
                return
            self.visible_check.setChecked(not bool(getattr(node, "_gr_hidden", False)))
            self._set_combo_value(self.category_combo, str(getattr(node, "_gr_sprite_category", "") or ""))
            self._set_combo_value(self.mode_combo, self._render_mode(node))
            self.cutoff_spin.setValue(self._alpha_cutoff(node))
            self.opacity_spin.setValue(self._opacity(node))
            self.decal_check.setChecked(bool(getattr(node, "txi_decal", False)))
            self.key_matte_check.setChecked(self._uses_matte_key(node))
            self.glow_spin.setValue(self._glow_boost(node))
        finally:
            self._updating = False

    def _apply_editor(self, *, apply_category_preset: bool = False) -> None:
        if self._updating:
            return
        nodes = self.selected_sprites()
        if not nodes:
            return
        mode = str(self.mode_combo.currentData() or "auto")
        category = str(self.category_combo.currentData() or "")
        cutoff = float(self.cutoff_spin.value())
        opacity = float(self.opacity_spin.value())
        hidden = not bool(self.visible_check.isChecked())
        decal = bool(self.decal_check.isChecked())
        alpha_source = "luminance" if self.key_matte_check.isChecked() else ""
        glow = float(self.glow_spin.value())
        if apply_category_preset:
            preset = self._CATEGORY_PRESETS.get(category)
            if preset is None:
                mode = "auto"
                alpha_source = ""
                glow = 0.0
            else:
                mode = str(preset["mode"])
                cutoff = float(preset["cutoff"])
                opacity = float(preset["opacity"])
                decal = bool(preset["decal"])
                alpha_source = str(preset["alpha_source"])
                glow = float(preset["glow"])
            self._sync_editor_preset(mode, cutoff, opacity, decal, alpha_source, glow)
        changed = []
        for node in nodes:
            self._remember_original(node)
            setattr(node, "_gr_sprite_category", category)
            setattr(node, "_gr_hidden", hidden)
            if mode == "auto":
                if hasattr(node, "_gr_sprite_render_mode"):
                    try:
                        delattr(node, "_gr_sprite_render_mode")
                    except Exception:
                        setattr(node, "_gr_sprite_render_mode", "")
                self._restore_original(node)
            else:
                setattr(node, "_gr_sprite_render_mode", mode)
                self._apply_render_mode(node, mode, cutoff, opacity, decal)
            setattr(node, "_gr_sprite_alpha_source", alpha_source)
            setattr(node, "_gr_sprite_glow", max(0.0, min(4.0, glow)))
            self._bump_revision(node)
            changed.append(node)
        self.refresh()
        self._emit_changed(changed)

    def _apply_render_mode(self, node, mode: str, cutoff: float, opacity: float, decal: bool) -> None:
        setattr(node, "txi_alpha_test", max(0.0, min(1.0, cutoff)))
        setattr(node, "txi_decal", bool(decal))
        setattr(node, "alpha", max(0.0, min(1.0, opacity)))
        if mode == "opaque":
            setattr(node, "txi_blending", 0)
            setattr(node, "transparency_hint", 0)
            setattr(node, "txi_wateralpha", 1.0)
            setattr(node, "alpha", 1.0)
            setattr(node, "txi_decal", False)
        elif mode == "cutout":
            setattr(node, "txi_blending", 2)
            setattr(node, "transparency_hint", max(1, int(getattr(node, "transparency_hint", 0) or 0)))
            setattr(node, "txi_wateralpha", 1.0)
            setattr(node, "alpha", 1.0)
        elif mode == "blend":
            setattr(node, "txi_blending", 0)
            setattr(node, "transparency_hint", max(1, int(getattr(node, "transparency_hint", 0) or 0)))
            setattr(node, "txi_wateralpha", max(0.0, min(1.0, opacity)))
        elif mode == "additive":
            setattr(node, "txi_blending", 1)
            setattr(node, "transparency_hint", max(1, int(getattr(node, "transparency_hint", 0) or 0)))
            setattr(node, "txi_wateralpha", 1.0)
        elif mode == "lighten":
            setattr(node, "txi_blending", 3)
            setattr(node, "transparency_hint", max(1, int(getattr(node, "transparency_hint", 0) or 0)))
            setattr(node, "txi_wateralpha", 1.0)

    def _set_selected_hidden(self, hidden: bool) -> None:
        changed = []
        for node in self.selected_sprites():
            if bool(getattr(node, "_gr_hidden", False)) == hidden:
                continue
            setattr(node, "_gr_hidden", bool(hidden))
            self._bump_revision(node)
            changed.append(node)
        if changed:
            self.refresh()
            self._emit_changed(changed)

    def _sync_editor_preset(self, mode: str, cutoff: float, opacity: float, decal: bool, alpha_source: str, glow: float) -> None:
        self._updating = True
        try:
            self._set_combo_value(self.mode_combo, mode)
            self.cutoff_spin.setValue(max(0.0, min(1.0, float(cutoff))))
            self.opacity_spin.setValue(max(0.0, min(1.0, float(opacity))))
            self.decal_check.setChecked(bool(decal))
            self.key_matte_check.setChecked(bool(alpha_source))
            self.glow_spin.setValue(max(0.0, min(4.0, float(glow))))
        finally:
            self._updating = False

    def _isolate_selected(self) -> None:
        keep = {id(node) for node in self.selected_sprites()}
        if not keep:
            return
        changed = []
        for node in self._mesh_nodes():
            hidden = id(node) not in keep
            if bool(getattr(node, "_gr_hidden", False)) != hidden:
                setattr(node, "_gr_hidden", hidden)
                self._bump_revision(node)
                changed.append(node)
        if changed:
            self.refresh()
            self._emit_changed(changed)

    def _reset_selected(self) -> None:
        self._reset_nodes(self.selected_sprites())

    def _reset_all(self) -> None:
        self._reset_nodes(self._mesh_nodes())

    def _reset_nodes(self, nodes: list) -> None:
        changed = []
        for node in nodes:
            restored = self._restore_original(node)
            was_hidden = bool(getattr(node, "_gr_hidden", False))
            had_category = bool(getattr(node, "_gr_sprite_category", "") or "")
            if restored or was_hidden or had_category:
                setattr(node, "_gr_hidden", False)
                setattr(node, "_gr_sprite_category", "")
                self._bump_revision(node)
                changed.append(node)
        if changed:
            self.refresh()
            self._emit_changed(changed)

    def _select_current(self) -> None:
        selected = self.selected_sprites()
        if selected:
            self.spriteSelected.emit(selected[-1])

    def _filter_rows(self, text: str) -> None:
        needle = text.lower().strip()
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            haystack = " ".join(item.text(column) for column in range(self.tree.columnCount())).lower()
            item.setHidden(bool(needle and needle not in haystack))

    def _resize_columns(self) -> None:
        for column in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(column)

    def _set_editor_enabled(self, enabled: bool) -> None:
        for widget in (
            self.visible_check,
            self.category_combo,
            self.mode_combo,
            self.cutoff_spin,
            self.opacity_spin,
            self.decal_check,
            self.key_matte_check,
            self.glow_spin,
        ):
            widget.setEnabled(enabled)

    def _set_combo_value(self, combo: QtWidgets.QComboBox, value: str) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def _emit_changed(self, nodes: list) -> None:
        self.spriteRenderChanged.emit(list(nodes or []))

    def _remember_original(self, node) -> None:
        if hasattr(node, "_gr_sprite_original_material"):
            return
        setattr(node, "_gr_sprite_original_material", {name: getattr(node, name, None) for name in self._ORIGINAL_ATTRS})

    def _restore_original(self, node) -> bool:
        original = getattr(node, "_gr_sprite_original_material", None)
        if not isinstance(original, dict):
            return False
        for name, value in original.items():
            if value is None and hasattr(node, name):
                try:
                    delattr(node, name)
                except Exception:
                    setattr(node, name, value)
            else:
                setattr(node, name, value)
        return True

    def _bump_revision(self, node) -> None:
        try:
            setattr(node, "_gr_revision", int(getattr(node, "_gr_revision", 0) or 0) + 1)
        except Exception:
            setattr(node, "_gr_revision", 1)

    def _is_sprite_candidate(self, node) -> bool:
        if not getattr(node, "is_mesh", False):
            return False
        if self._is_saber_hilt(node):
            return True
        if bool(getattr(node, "is_dangly", False)):
            return True
        if int(getattr(node, "transparency_hint", 0) or 0) > 0:
            return True
        if int(getattr(node, "txi_blending", 0) or 0) in (1, 2, 3):
            return True
        if float(getattr(node, "txi_alpha_test", 0.0) or 0.0) > 0.0:
            return True
        if float(getattr(node, "txi_wateralpha", 1.0) or 1.0) < 0.999:
            return True
        if bool(getattr(node, "txi_decal", False)):
            return True
        if float(getattr(node, "alpha", 1.0) or 1.0) < 0.999:
            return True
        text = f"{getattr(node, 'name', '')} {self._texture_name(node)}".lower()
        keywords = (
            "fur",
            "hair",
            "grass",
            "leaf",
            "leav",
            "vine",
            "branch",
            "tree",
            "window",
            "glass",
            "pane",
            "saber",
            "sabre",
            "lsabre",
            "blade",
            "glow",
            "flare",
            "beam",
            "sprite",
            "card",
            "decal",
        )
        return any(keyword in text for keyword in keywords)

    def _render_mode(self, node) -> str:
        explicit = str(getattr(node, "_gr_sprite_render_mode", "") or "").lower()
        if explicit in {"opaque", "cutout", "blend", "additive", "lighten"}:
            return explicit
        if self._is_saber_hilt(node):
            return "opaque"
        if self._auto_uses_matte_key(node):
            return "lighten"
        blend = int(getattr(node, "txi_blending", 0) or 0)
        if blend == 1:
            return "additive"
        if blend == 2:
            return "cutout"
        if blend == 3:
            return "lighten"
        if (
            float(getattr(node, "txi_wateralpha", 1.0) or 1.0) < 0.999
            or float(getattr(node, "alpha", 1.0) or 1.0) < 0.999
            or bool(getattr(node, "txi_decal", False))
        ):
            return "blend"
        if int(getattr(node, "transparency_hint", 0) or 0) > 0 or float(getattr(node, "txi_alpha_test", 0.0) or 0.0) > 0.0:
            return "cutout"
        return "opaque"

    def _mode_label(self, mode: str) -> str:
        return {
            "opaque": "Opaque",
            "cutout": "Cutout",
            "blend": "Blend",
            "additive": "Additive",
            "lighten": "Lighten",
        }.get(mode, "Auto")

    def _category_label(self, node) -> str:
        value = str(getattr(node, "_gr_sprite_category", "") or "")
        if value:
            return {
                "fur_hair": "Fur / Hair",
                "hilt": "Hilt",
                "foliage": "Foliage",
                "glass_window": "Glass / Window",
                "glow_blade": "Glow / Blade",
                "decal": "Decal",
                "sprite": "Other Sprite",
            }.get(value, value)
        text = f"{getattr(node, 'name', '')} {self._texture_name(node)}".lower()
        if self._is_saber_hilt(node):
            return "Hilt"
        if any(token in text for token in ("fur", "hair")):
            return "Fur / Hair"
        if any(token in text for token in ("grass", "leaf", "leav", "vine", "branch", "tree")):
            return "Foliage"
        if any(token in text for token in ("window", "glass", "pane")):
            return "Glass / Window"
        if any(token in text for token in ("saber", "sabre", "lsabre", "blade", "glow", "flare", "beam")):
            return "Glow / Blade"
        if "decal" in text or bool(getattr(node, "txi_decal", False)):
            return "Decal"
        return "Sprite"

    def _texture_name(self, node) -> str:
        texture = str(getattr(node, "texture", "") or "")
        if texture:
            return texture
        names = getattr(node, "texture_names", None) or []
        return str(names[0]) if names else ""

    def _has_valid_texture(self, node) -> bool:
        texture = self._texture_name(node).strip()
        return bool(texture and texture.lower() not in {"null", "none", "(none)"})

    def _node_role(self, node) -> str:
        return node_browser_role(node, str(getattr(node, "type_label", "") or "node"))

    def _alpha_cutoff(self, node) -> float:
        value = float(getattr(node, "txi_alpha_test", 0.0) or 0.0)
        return max(0.0, min(1.0, value if value > 0.0 else 0.5))

    def _opacity(self, node) -> float:
        alpha = float(getattr(node, "alpha", 1.0) or 1.0)
        water = float(getattr(node, "txi_wateralpha", 1.0) or 1.0)
        return max(0.0, min(1.0, min(alpha, water)))

    def _flag_label(self, node) -> str:
        flags = []
        blend = int(getattr(node, "txi_blending", 0) or 0)
        if blend:
            flags.append(f"blend {blend}")
        hint = int(getattr(node, "transparency_hint", 0) or 0)
        if hint:
            flags.append(f"hint {hint}")
        if bool(getattr(node, "txi_decal", False)):
            flags.append("decal")
        if bool(getattr(node, "is_dangly", False)):
            flags.append("dangly")
        if getattr(node, "txi_envmaptexture", ""):
            flags.append("env")
        if self._is_saber_hilt(node):
            flags.append("hilt")
        if self._uses_matte_key(node):
            flags.append("key")
        glow = self._glow_boost(node)
        if glow > 0.001:
            flags.append(f"glow {glow:.1f}")
        return ", ".join(flags)

    def _tooltip(self, node) -> str:
        return "\n".join(
            [
                f"Mesh: {getattr(node, 'name', '')}",
                f"Texture: {self._texture_name(node) or '(none)'}",
                f"Mode: {self._mode_label(self._render_mode(node))}",
                f"Cutoff: {self._alpha_cutoff(node):.3f}",
                f"Opacity: {self._opacity(node):.3f}",
                f"Flags: {self._flag_label(node) or '(none)'}",
            ]
        )

    def _uses_matte_key(self, node) -> bool:
        source = str(getattr(node, "_gr_sprite_alpha_source", "") or "").lower()
        if source in {"luminance", "brightness", "matte", "black_key"}:
            return True
        return self._auto_uses_matte_key(node)

    def _auto_uses_matte_key(self, node) -> bool:
        if self._is_saber_hilt(node):
            return False
        text = f"{getattr(node, 'name', '')} {self._texture_name(node)}".lower()
        return any(token in text for token in ("saber", "sabre", "lsabre", "blade", "glow", "flare", "beam"))

    def _is_saber_hilt(self, node) -> bool:
        name = str(getattr(node, "name", "") or "").lower()
        texture = self._texture_name(node).lower()
        if texture.startswith(("w_lghtsbr", "w_shortsbr", "w_dblsbr")):
            return True
        return name.startswith(("lghtsbr", "lshandle")) or "handle" in name

    def _glow_boost(self, node) -> float:
        explicit = getattr(node, "_gr_sprite_glow", None)
        if explicit is not None:
            try:
                return max(0.0, min(4.0, float(explicit)))
            except Exception:
                return 0.0
        return 1.6 if self._auto_uses_matte_key(node) else 0.0

    def _sprite_icon(self, node) -> QtGui.QIcon:
        palette = self.palette()
        color = palette.color(QtGui.QPalette.Highlight)
        if self._render_mode(node) in {"additive", "lighten"}:
            color = palette.color(QtGui.QPalette.Link)
        elif self._render_mode(node) == "cutout":
            color = palette.color(QtGui.QPalette.ToolTipBase)
        pix = QtGui.QPixmap(16, 16)
        pix.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pix)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setPen(QtGui.QPen(color, 1.4))
        fill = QtGui.QColor(color)
        fill.setAlpha(95)
        painter.setBrush(fill)
        painter.drawRect(3, 3, 10, 10)
        painter.drawLine(5, 5, 12, 12)
        painter.drawLine(12, 5, 5, 12)
        painter.end()
        return QtGui.QIcon(pix)
