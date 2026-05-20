"""Qt skeleton and properties panels for the GhostRigger migration."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.gui.qt_lib.assets.qt_theme import C, heading

# ── CharacterMode wiring (M1 / T105) ────────────────────────────────────────
# Imported lazily-safe: ``model_data`` is a pure-Python module but the
# enclosing ``src.core`` package imports the pykotor loader stack at
# import time.  We isolate the failure so the Qt panel still loads in
# environments where pykotor is missing (the badge simply stays empty).
try:
    from src.core.model_data import CharacterMode, detect_character_mode
    _CHARACTER_MODE_AVAILABLE = True
except Exception:                                       # pragma: no cover
    CharacterMode = None                                # type: ignore[assignment]
    detect_character_mode = None                        # type: ignore[assignment]
    _CHARACTER_MODE_AVAILABLE = False


# Accent colour per CharacterMode for the badge background.  Keys must
# match :attr:`CharacterMode.icon_key` so future icon assets line up.
_CHARACTER_MODE_BADGE_COLORS = {
    "mode_headless_body": "#3FA9F5",   # blue
    "mode_head":          "#F5A623",   # amber
    "mode_humanoid":      "#00A8A8",   # teal
    "mode_supermodel":    "#9B59B6",   # purple
    "mode_creature":      "#27AE60",   # green
    "mode_ambiguous":     "#7F8C8D",   # grey
    "mode_unsupported":   "#C0392B",   # red
}


class QtSkeletonPanel(QtWidgets.QWidget):
    nodeSelected = QtCore.Signal(object)
    nodesSelected = QtCore.Signal(list)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._all_items: dict[QtWidgets.QTreeWidgetItem, object] = {}
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        header = QtWidgets.QHBoxLayout()
        header.addWidget(heading("Skeleton / Nodes"))
        self.count_label = QtWidgets.QLabel("")
        self.count_label.setStyleSheet(f"color:{C['text2']}; font-size:8pt;")
        header.addWidget(self.count_label)
        root.addLayout(header)

        search_row = QtWidgets.QHBoxLayout()
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search nodes")
        self.search_edit.textChanged.connect(self._filter)
        clear = QtWidgets.QPushButton("x")
        clear.setProperty("compact", True)
        clear.clicked.connect(self.search_edit.clear)
        search_row.addWidget(self.search_edit)
        search_row.addWidget(clear)
        root.addLayout(search_row)

        action_row = QtWidgets.QHBoxLayout()
        select_all = QtWidgets.QPushButton("Select All Bones")
        select_all.setProperty("compact", True)
        select_all.clicked.connect(self.select_all_nodes)
        clear_sel = QtWidgets.QPushButton("Clear")
        clear_sel.setProperty("compact", True)
        clear_sel.clicked.connect(self.clear_selection)
        self.selection_label = QtWidgets.QLabel("")
        self.selection_label.setStyleSheet(f"color:{C['gold']}; font-size:8pt;")
        action_row.addWidget(select_all)
        action_row.addWidget(clear_sel)
        action_row.addStretch(1)
        action_row.addWidget(self.selection_label)
        root.addLayout(action_row)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Type", "Verts", "Faces"])
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        root.addWidget(self.tree, 1)

    def load_model(self, model) -> None:
        self.tree.clear()
        self._all_items.clear()
        if not model or not getattr(model, "root_node", None):
            self.count_label.setText("")
            return
        n_nodes = model.node_count() if hasattr(model, "node_count") else 0
        n_mesh = len(model.mesh_nodes()) if hasattr(model, "mesh_nodes") else 0
        self.count_label.setText(f"{n_nodes} nodes  {n_mesh} mesh")
        self._insert_node_iterative(model.root_node)
        self.tree.expandToDepth(0)

    def _insert_node_iterative(self, root_node) -> None:
        icon_map = {
            "trimesh": "[M]",
            "skin": "[S]",
            "danglymesh": "[D]",
            "dummy": "[.]",
            "light": "[L]",
            "emitter": "[E]",
            "lightsaber": "[B]",
            "reference": "[R]",
        }
        stack = [(root_node, None)]
        while stack:
            node, parent_item = stack.pop()
            node_type = getattr(node, "type_label", "")
            icon = icon_map.get(node_type, "*")
            verts = len(getattr(node, "vertices", []) or []) if getattr(node, "is_mesh", False) else ""
            faces = len(getattr(node, "faces", []) or []) if getattr(node, "is_mesh", False) else ""
            item = QtWidgets.QTreeWidgetItem([
                f"{icon} {getattr(node, 'name', '')}",
                str(node_type),
                str(verts),
                str(faces),
            ])
            if parent_item is None:
                self.tree.addTopLevelItem(item)
            else:
                parent_item.addChild(item)
            self._all_items[item] = node
            for child in reversed(getattr(node, "children", []) or []):
                stack.append((child, item))

    def _on_selection_changed(self) -> None:
        selected = self.tree.selectedItems()
        self.selection_label.setText(f"{len(selected)} selected" if len(selected) > 1 else "")
        nodes = [self._all_items[item] for item in selected if item in self._all_items]
        if nodes:
            self.nodeSelected.emit(nodes[0])
        if len(nodes) > 1:
            self.nodesSelected.emit(nodes)

    def _filter(self, text: str) -> None:
        needle = text.lower().strip()
        if not needle:
            for item in self._all_items:
                item.setHidden(False)
            return
        for item, node in self._all_items.items():
            name = getattr(node, "name", "").lower()
            item.setHidden(needle not in name)

    def select_all_nodes(self) -> None:
        self.tree.selectAll()

    def clear_selection(self) -> None:
        self.tree.clearSelection()

    def select_node(self, node) -> None:
        for item, candidate in self._all_items.items():
            if candidate is node:
                self.tree.setCurrentItem(item)
                item.setSelected(True)
                break

    def get_selected_nodes(self) -> list:
        return [self._all_items[item] for item in self.tree.selectedItems() if item in self._all_items]


class QtPropertiesPanel(QtWidgets.QWidget):
    positionApplied = QtCore.Signal(object, float, float, float)
    moduleMeshSelected = QtCore.Signal(object)
    moduleMeshesSelected = QtCore.Signal(list)
    moduleMeshVisibilityChanged = QtCore.Signal()
    # Emitted whenever the user manually overrides the CharacterMode via
    # the override QComboBox.  Payload: the new :class:`CharacterMode`
    # value (or ``None`` when the enum isn't importable).  The Character
    # Builder toolbar / scene controller should connect to this and call
    # ``scene.set_mode(mode, locked=True)`` to honour the choice.
    characterModeChanged = QtCore.Signal(object)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._current_node = None
        self._current_model = None
        self._mesh_items: dict[QtWidgets.QTreeWidgetItem, object] = {}
        self._walkmesh_items: dict[QtWidgets.QTreeWidgetItem, object] = {}
        self._suppress_mesh_signal = False
        self._suppress_mode_signal = False
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)
        root.addWidget(heading("Properties"))

        # ── CharacterMode badge + override (M1 / T105) ────────────────────
        self._build_character_mode_row(root)

        self.tabs = QtWidgets.QTabWidget()
        self.text = QtWidgets.QTextEdit()
        self.text.setReadOnly(True)
        self.text.setPlainText("No model loaded.")
        self.tabs.addTab(self.text, "General")
        self.module_tab = self._build_module_mesh_tab()
        self.tabs.addTab(self.module_tab, "Module Meshes")
        root.addWidget(self.tabs, 1)

        transform = QtWidgets.QGroupBox("Node Transform (editable)")
        transform.setStyleSheet(f"QGroupBox {{ color:{C['gold']}; }}")
        form = QtWidgets.QGridLayout(transform)
        form.addWidget(QtWidgets.QLabel("Pos:"), 0, 0)
        self.x_spin = self._spin()
        self.y_spin = self._spin()
        self.z_spin = self._spin()
        for col, (label, spin) in enumerate((("X", self.x_spin), ("Y", self.y_spin), ("Z", self.z_spin)), start=1):
            box = QtWidgets.QHBoxLayout()
            box.addWidget(QtWidgets.QLabel(f"{label}:"))
            box.addWidget(spin)
            form.addLayout(box, 0, col)
        apply_button = QtWidgets.QPushButton("Apply Position")
        apply_button.clicked.connect(self._apply_transform)
        form.addWidget(apply_button, 1, 0, 1, 4)
        root.addWidget(transform)

    def _build_module_mesh_tab(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.module_browser_tabs = QtWidgets.QTabWidget()
        mesh_page = QtWidgets.QWidget()
        mesh_layout = QtWidgets.QVBoxLayout(mesh_page)
        mesh_layout.setContentsMargins(2, 2, 2, 2)
        mesh_layout.setSpacing(4)
        self.module_mesh_count = QtWidgets.QLabel("No module meshes.")
        self.module_mesh_count.setStyleSheet(f"color:{C['text2']};")
        mesh_layout.addWidget(self.module_mesh_count)

        self.module_mesh_filter = QtWidgets.QLineEdit()
        self.module_mesh_filter.setPlaceholderText("Filter meshes")
        self.module_mesh_filter.textChanged.connect(self._filter_module_meshes)
        mesh_layout.addWidget(self.module_mesh_filter)

        self.module_mesh_tree = QtWidgets.QTreeWidget()
        self.module_mesh_tree.setColumnCount(6)
        self.module_mesh_tree.setHeaderLabels(["Mesh", "Verts", "Faces", "Texture", "Visible", "Group"])
        self.module_mesh_tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.module_mesh_tree.itemSelectionChanged.connect(self._on_module_mesh_selection_changed)
        self.module_mesh_tree.setRootIsDecorated(False)
        self.module_mesh_tree.setAlternatingRowColors(True)
        mesh_layout.addWidget(self.module_mesh_tree, 1)
        select_all_shortcut = QtGui.QShortcut(QtGui.QKeySequence.SelectAll, self.module_mesh_tree)
        select_all_shortcut.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
        select_all_shortcut.activated.connect(self.select_all_module_meshes)

        walk_page = QtWidgets.QWidget()
        walk_layout = QtWidgets.QVBoxLayout(walk_page)
        walk_layout.setContentsMargins(2, 2, 2, 2)
        walk_layout.setSpacing(4)
        self.module_walkmesh_count = QtWidgets.QLabel("No walkmeshes.")
        self.module_walkmesh_count.setStyleSheet(f"color:{C['text2']};")
        walk_layout.addWidget(self.module_walkmesh_count)

        self.module_walkmesh_filter = QtWidgets.QLineEdit()
        self.module_walkmesh_filter.setPlaceholderText("Filter walkmeshes")
        self.module_walkmesh_filter.textChanged.connect(self._filter_module_meshes)
        walk_layout.addWidget(self.module_walkmesh_filter)

        self.module_walkmesh_tree = QtWidgets.QTreeWidget()
        self.module_walkmesh_tree.setColumnCount(6)
        self.module_walkmesh_tree.setHeaderLabels(["Walkmesh", "Verts", "Faces", "Texture", "Visible", "Group"])
        self.module_walkmesh_tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.module_walkmesh_tree.itemSelectionChanged.connect(self._on_module_mesh_selection_changed)
        self.module_walkmesh_tree.setRootIsDecorated(False)
        self.module_walkmesh_tree.setAlternatingRowColors(True)
        walk_layout.addWidget(self.module_walkmesh_tree, 1)
        select_all_walk_shortcut = QtGui.QShortcut(QtGui.QKeySequence.SelectAll, self.module_walkmesh_tree)
        select_all_walk_shortcut.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
        select_all_walk_shortcut.activated.connect(self.select_all_module_meshes)

        self.module_browser_tabs.addTab(mesh_page, "Meshes")
        self.module_browser_tabs.addTab(walk_page, "Walkmeshes")
        layout.addWidget(self.module_browser_tabs, 1)

        actions = QtWidgets.QGridLayout()
        actions.setHorizontalSpacing(4)
        actions.setVerticalSpacing(4)
        self.hide_mesh_button = QtWidgets.QPushButton("Hide")
        self.unhide_mesh_button = QtWidgets.QPushButton("Unhide")
        self.hide_unselected_button = QtWidgets.QPushButton("Hide Unselected")
        self.unhide_all_button = QtWidgets.QPushButton("Unhide All")
        self.selection_set_button = QtWidgets.QPushButton("Create Selection Set")
        self.mesh_group_button = QtWidgets.QPushButton("Create Mesh Group")
        self.hide_mesh_button.clicked.connect(lambda: self._set_selected_meshes_hidden(True))
        self.unhide_mesh_button.clicked.connect(lambda: self._set_selected_meshes_hidden(False))
        self.hide_unselected_button.clicked.connect(self._hide_unselected_module_meshes)
        self.unhide_all_button.clicked.connect(self._unhide_all_module_meshes)
        self.selection_set_button.clicked.connect(self._create_selection_set_from_panel)
        self.mesh_group_button.clicked.connect(self._create_mesh_group_from_panel)
        for index, widget in enumerate((
            self.hide_mesh_button,
            self.unhide_mesh_button,
            self.hide_unselected_button,
            self.unhide_all_button,
            self.selection_set_button,
            self.mesh_group_button,
        )):
            actions.addWidget(widget, index // 2, index % 2)
        layout.addLayout(actions)
        return page

    def _spin(self) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(-100000.0, 100000.0)
        spin.setDecimals(5)
        spin.setSingleStep(0.05)
        return spin

    # ── CharacterMode UI (M1 / T105) ──────────────────────────────────────────

    def _build_character_mode_row(self, parent_layout: QtWidgets.QBoxLayout) -> None:
        """Construct the read-only badge + manual-override combo row.

        Layout::

            [ Mode: ] [ ●● HEADLESS BODY ●● ]   [Override ▾]

        The badge displays the auto-detected mode with a colour swatch
        from :data:`_CHARACTER_MODE_BADGE_COLORS`.  The combo lets the
        user pin a different mode; selecting "(Auto)" clears the lock
        and emits :attr:`characterModeChanged` with ``None``.
        """
        group = QtWidgets.QGroupBox("Character Mode")
        group.setStyleSheet(f"QGroupBox {{ color:{C['gold']}; }}")
        grid = QtWidgets.QGridLayout(group)
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setHorizontalSpacing(6)

        # ── Read-only badge ─────────────────────────────────────────────
        self.character_mode_badge = QtWidgets.QLabel("(unknown)")
        self.character_mode_badge.setAlignment(QtCore.Qt.AlignCenter)
        self.character_mode_badge.setMinimumWidth(140)
        self.character_mode_badge.setStyleSheet(
            "QLabel { "
            f"background:{_CHARACTER_MODE_BADGE_COLORS['mode_ambiguous']}; "
            "color:#FFFFFF; "
            "padding:2px 8px; "
            "border-radius:6px; "
            "font-weight:bold; "
            "}"
        )
        grid.addWidget(QtWidgets.QLabel("Detected:"), 0, 0)
        grid.addWidget(self.character_mode_badge, 0, 1)

        # ── Manual-override combo ───────────────────────────────────────
        self.character_mode_combo = QtWidgets.QComboBox()
        # Index 0 is always "(Auto)" — represents "no override / use
        # detected value".  The remaining entries enumerate CharacterMode.
        self.character_mode_combo.addItem("(Auto)", userData=None)
        if _CHARACTER_MODE_AVAILABLE and CharacterMode is not None:
            for mode in CharacterMode:
                self.character_mode_combo.addItem(mode.display_name,
                                                  userData=mode)
        else:
            self.character_mode_combo.setEnabled(False)
            self.character_mode_combo.setToolTip(
                "CharacterMode enum unavailable (pykotor not installed?)"
            )
        self.character_mode_combo.currentIndexChanged.connect(
            self._on_mode_override_changed
        )
        grid.addWidget(QtWidgets.QLabel("Override:"), 1, 0)
        grid.addWidget(self.character_mode_combo, 1, 1)

        parent_layout.addWidget(group)

    def _update_character_mode_badge(self, mode) -> None:
        """Refresh the badge label + colour to reflect *mode*.

        Accepts a :class:`CharacterMode`, ``None`` (clears the badge),
        or any value with a ``.display_name`` / ``.icon_key`` interface
        for forward compatibility.
        """
        if mode is None:
            self.character_mode_badge.setText("(unknown)")
            color = _CHARACTER_MODE_BADGE_COLORS["mode_ambiguous"]
        else:
            display = getattr(mode, "display_name", str(mode))
            icon_key = getattr(mode, "icon_key", "mode_ambiguous")
            color = _CHARACTER_MODE_BADGE_COLORS.get(
                icon_key, _CHARACTER_MODE_BADGE_COLORS["mode_ambiguous"]
            )
            self.character_mode_badge.setText(display.upper())

        self.character_mode_badge.setStyleSheet(
            "QLabel { "
            f"background:{color}; "
            "color:#FFFFFF; "
            "padding:2px 8px; "
            "border-radius:6px; "
            "font-weight:bold; "
            "}"
        )

    def set_character_mode(self, mode, *, from_scene: bool = False) -> None:
        """Public API: update the badge + combo to reflect a known mode.

        Call this whenever the underlying scene's CharacterMode changes
        (e.g. after a slot edit, or after :meth:`CharacterScene.set_mode`).

        Parameters
        ----------
        mode      : :class:`CharacterMode` value (or ``None`` for "unknown").
        from_scene: When True, suppresses the :attr:`characterModeChanged`
                    signal so the panel doesn't echo back to the scene
                    that just notified it.
        """
        self._update_character_mode_badge(mode)
        if from_scene:
            self._suppress_mode_signal = True
        try:
            # Match the combo selection to the new mode; "(Auto)" stays
            # selected when caller passes None.
            if mode is None:
                self.character_mode_combo.setCurrentIndex(0)
            else:
                for i in range(self.character_mode_combo.count()):
                    if self.character_mode_combo.itemData(i) is mode:
                        self.character_mode_combo.setCurrentIndex(i)
                        break
        finally:
            self._suppress_mode_signal = False

    def _on_mode_override_changed(self, index: int) -> None:
        """Emit :attr:`characterModeChanged` when the user picks an entry.

        Selecting "(Auto)" emits ``None`` so the scene can unlock its
        mode and fall back to auto-detection.
        """
        if self._suppress_mode_signal:
            return
        mode = self.character_mode_combo.itemData(index)
        # Reflect the user's choice in the badge immediately.  When mode
        # is None ("(Auto)"), recompute from the current model so the
        # badge stays informative.
        if mode is None and self._current_model is not None and detect_character_mode is not None:
            try:
                detected = detect_character_mode(self._current_model)
            except Exception:                              # pragma: no cover
                detected = None
            self._update_character_mode_badge(detected)
        else:
            self._update_character_mode_badge(mode)
        self.characterModeChanged.emit(mode)

    def _apply_transform(self) -> None:
        node = self._current_node
        if not node:
            return
        x, y, z = self.x_spin.value(), self.y_spin.value(), self.z_spin.value()
        try:
            before = (
                tuple(getattr(node, "position", (0.0, 0.0, 0.0))),
                tuple(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))),
            )
            setattr(node, "_gr_undo_before_transform", before)
            node.position = (x, y, z)
        finally:
            self.positionApplied.emit(node, x, y, z)

    def show_model(self, model) -> None:
        if not model:
            self._current_model = None
            self._current_node = None
            self.text.setPlainText("No model loaded.")
            self._populate_module_meshes([])
            self._update_character_mode_badge(None)
            self._suppress_mode_signal = True
            try:
                self.character_mode_combo.setCurrentIndex(0)
            finally:
                self._suppress_mode_signal = False
            return
        self._current_model = model
        # Auto-detect CharacterMode for the badge (panel-level preview).
        # The owning scene/toolbar still drives the canonical mode via
        # set_character_mode() — this is a best-effort live indicator.
        if detect_character_mode is not None:
            try:
                detected = detect_character_mode(model)
            except Exception:                              # pragma: no cover
                detected = None
            self._update_character_mode_badge(detected)
            # Sync combo to the detected value (unless user already locked
            # an override — represented by a non-zero combo index that
            # doesn't match the detected mode; we leave that alone).
            if self.character_mode_combo.currentIndex() == 0:
                self._suppress_mode_signal = True
                try:
                    for i in range(self.character_mode_combo.count()):
                        if self.character_mode_combo.itemData(i) is detected:
                            # Only reflect in badge; keep combo at "(Auto)"
                            # so the override semantics stay unambiguous.
                            break
                finally:
                    self._suppress_mode_signal = False
        mesh_nodes = model.mesh_nodes() if hasattr(model, "mesh_nodes") else []
        all_nodes = model.all_nodes() if hasattr(model, "all_nodes") else []
        module_mesh_nodes = self._module_mesh_candidates(model, mesh_nodes, all_nodes)
        bone_nodes = model.bone_nodes() if hasattr(model, "bone_nodes") else []
        textures = model.texture_list() if hasattr(model, "texture_list") else []
        total_verts = sum(len(getattr(node, "vertices", []) or []) for node in mesh_nodes)
        total_faces = sum(len(getattr(node, "faces", []) or []) for node in mesh_nodes)
        lines = [
            f"Model: {getattr(model, 'name', '')}",
            f"Game:  {getattr(getattr(model, 'game_version', ''), 'name', getattr(model, 'game_version', ''))}",
            f"Super: {getattr(model, 'supermodel', '')}",
            f"Type:  {getattr(model, 'classification', '')}",
            "",
            "-- Hierarchy --",
            f"Nodes: {len(all_nodes) if all_nodes else getattr(model, 'node_count', lambda: 0)()}",
            f"Mesh:  {len(mesh_nodes)}",
            f"Bones: {len(bone_nodes)}",
            f"Anims: {len(getattr(model, 'animations', []) or [])}",
            "",
            "-- Geometry --",
            f"Verts: {total_verts:,}",
            f"Faces: {total_faces:,}",
            f"Texs:  {len(textures)}",
            "",
            "-- Textures --",
            *[f"  {tex}" for tex in textures],
        ]
        self.text.setPlainText("\n".join(lines))
        self._populate_module_meshes(module_mesh_nodes)

    def show_node(self, node) -> None:
        self._current_node = node
        if node is None:
            if self._current_model is not None:
                self.show_model(self._current_model)
            else:
                self.text.setPlainText("No model loaded.")
            return
        pos = getattr(node, "position", (0.0, 0.0, 0.0))
        rot = getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))
        self.x_spin.setValue(float(pos[0]))
        self.y_spin.setValue(float(pos[1]))
        self.z_spin.setValue(float(pos[2]))
        lines = [
            f"Node:  {getattr(node, 'name', '')}",
            f"Type:  {getattr(node, 'type_label', '')}",
            f"Pos:   ({pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f})",
            f"Rot:   ({rot[0]:.3f}, {rot[1]:.3f}, {rot[2]:.3f}, {rot[3]:.3f})",
        ]
        parent = getattr(node, "parent", None)
        if parent:
            lines.append(f"Parent:{getattr(parent, 'name', '')}")
        if self._is_module_mesh_candidate(node):
            lines += [
                "",
                "-- Mesh --",
                f"Verts: {len(getattr(node, 'vertices', []) or []):,}",
                f"Faces: {len(getattr(node, 'faces', []) or []):,}",
                f"Texture: {getattr(node, 'texture', '')}",
            ]
        self.text.setPlainText("\n".join(lines))
        self.select_module_mesh(node)

    def _mesh_label(self, node) -> str:
        return str(getattr(node, "name", "") or getattr(node, "id", "") or "<mesh>")

    def _is_module_mesh_candidate(self, node) -> bool:
        verts = getattr(node, "vertices", getattr(node, "verts", [])) or []
        faces = getattr(node, "faces", []) or []
        return bool(verts and faces)

    def _is_walkmesh_candidate(self, node) -> bool:
        name = self._mesh_label(node).lower()
        flags = int(getattr(node, "flags", 0) or 0)
        return (
            name.startswith("walkmesh")
            or int(getattr(node, "vertex_space", 0) or 0) == 2
            or bool(getattr(node, "is_aabb", False))
            or bool(flags & 0x0200)
        )

    def _module_mesh_candidates(self, model, mesh_nodes=None, all_nodes=None) -> list:
        candidates = []
        seen = set()
        for source in (mesh_nodes or [], all_nodes or []):
            for node in source or []:
                if node is None or id(node) in seen:
                    continue
                if not self._is_module_mesh_candidate(node):
                    continue
                seen.add(id(node))
                candidates.append(node)
        if not candidates and model is not None and hasattr(model, "all_nodes"):
            for node in model.all_nodes() or []:
                if node is not None and id(node) not in seen and self._is_module_mesh_candidate(node):
                    seen.add(id(node))
                    candidates.append(node)
        return candidates

    def _populate_module_meshes(self, mesh_nodes) -> None:
        self._suppress_mesh_signal = True
        try:
            self.module_mesh_tree.clear()
            self.module_walkmesh_tree.clear()
            self._mesh_items.clear()
            self._walkmesh_items.clear()
            for node in mesh_nodes or []:
                if not self._is_module_mesh_candidate(node):
                    continue
                verts = len(getattr(node, "vertices", []) or [])
                faces = len(getattr(node, "faces", []) or [])
                texture = str(getattr(node, "texture", "") or "")
                visible = "no" if getattr(node, "_gr_hidden", False) else "yes"
                group = str(getattr(node, "_gr_mesh_group", "") or "")
                item = QtWidgets.QTreeWidgetItem([
                    self._mesh_label(node),
                    f"{verts:,}",
                    f"{faces:,}",
                    texture,
                    visible,
                    group,
                ])
                item.setData(0, QtCore.Qt.UserRole, node)
                if visible == "no":
                    for column in range(self.module_mesh_tree.columnCount()):
                        item.setForeground(column, QtGui.QBrush(QtGui.QColor(C["text2"])))
                tree = self.module_walkmesh_tree if self._is_walkmesh_candidate(node) else self.module_mesh_tree
                items = self._walkmesh_items if tree is self.module_walkmesh_tree else self._mesh_items
                tree.addTopLevelItem(item)
                items[item] = node
            for tree in (self.module_mesh_tree, self.module_walkmesh_tree):
                for column in range(tree.columnCount()):
                    tree.resizeColumnToContents(column)
            count = self.module_mesh_tree.topLevelItemCount()
            self.module_mesh_count.setText(f"{count:,} module mesh(es)" if count else "No module meshes.")
            walk_count = self.module_walkmesh_tree.topLevelItemCount()
            self.module_walkmesh_count.setText(f"{walk_count:,} walkmesh(es)" if walk_count else "No walkmeshes.")
        finally:
            self._suppress_mesh_signal = False

    def _filter_module_meshes(self, text: str) -> None:
        for edit, items in (
            (self.module_mesh_filter, self._mesh_items),
            (self.module_walkmesh_filter, self._walkmesh_items),
        ):
            needle = (edit.text() or "").strip().lower()
            for item, node in items.items():
                haystack = " ".join([
                    self._mesh_label(node),
                    str(getattr(node, "texture", "") or ""),
                    str(getattr(node, "_gr_mesh_group", "") or ""),
                ]).lower()
                item.setHidden(needle not in haystack)

    def _selected_module_meshes(self) -> list:
        selected = []
        for tree, items in (
            (self.module_mesh_tree, self._mesh_items),
            (self.module_walkmesh_tree, self._walkmesh_items),
        ):
            selected.extend(items[item] for item in tree.selectedItems() if item in items)
        return selected

    def _on_module_mesh_selection_changed(self) -> None:
        if self._suppress_mesh_signal:
            return
        nodes = self._selected_module_meshes()
        node = nodes[0] if nodes else None
        self.moduleMeshesSelected.emit(nodes)
        if node is not None:
            self.moduleMeshSelected.emit(node)

    def select_module_mesh(self, node) -> None:
        self.select_module_meshes([node] if node is not None else [])

    def select_module_meshes(self, nodes: list) -> None:
        if self._suppress_mesh_signal:
            return
        node_ids = {id(node) for node in nodes if node is not None and self._is_module_mesh_candidate(node)}
        self._suppress_mesh_signal = True
        try:
            self.module_mesh_tree.clearSelection()
            self.module_walkmesh_tree.clearSelection()
            if not node_ids:
                return
            for tree, items, tab in (
                (self.module_mesh_tree, self._mesh_items, 0),
                (self.module_walkmesh_tree, self._walkmesh_items, 1),
            ):
                for item, candidate in items.items():
                    if id(candidate) in node_ids:
                        item.setSelected(True)
                        tree.setCurrentItem(item)
                        self.module_browser_tabs.setCurrentIndex(tab)
            self.tabs.setCurrentWidget(self.module_tab)
        finally:
            self._suppress_mesh_signal = False

    def select_all_module_meshes(self) -> None:
        if self.module_browser_tabs.currentWidget() is self.module_browser_tabs.widget(1):
            self.module_walkmesh_tree.selectAll()
        else:
            self.module_mesh_tree.selectAll()

    def _refresh_module_mesh_rows(self) -> None:
        for tree, items in (
            (self.module_mesh_tree, self._mesh_items),
            (self.module_walkmesh_tree, self._walkmesh_items),
        ):
            for item, node in items.items():
                hidden = bool(getattr(node, "_gr_hidden", False))
                item.setText(4, "no" if hidden else "yes")
                item.setText(5, str(getattr(node, "_gr_mesh_group", "") or ""))
                brush = QtGui.QBrush(QtGui.QColor(C["text2"] if hidden else C["text"]))
                for column in range(tree.columnCount()):
                    item.setForeground(column, brush)

    def refresh_module_mesh_rows(self) -> None:
        self._refresh_module_mesh_rows()

    def _set_meshes_hidden(self, nodes: list, hidden: bool) -> None:
        changed = False
        for node in nodes:
            if node is None:
                continue
            before = bool(getattr(node, "_gr_hidden", False))
            setattr(node, "_gr_hidden", bool(hidden))
            changed = changed or before != bool(hidden)
        self._refresh_module_mesh_rows()
        if changed:
            self.moduleMeshVisibilityChanged.emit()

    def _set_selected_meshes_hidden(self, hidden: bool) -> None:
        self._set_meshes_hidden(self._selected_module_meshes(), hidden)

    def _hide_unselected_module_meshes(self) -> None:
        selected = {id(node) for node in self._selected_module_meshes()}
        nodes = [
            node
            for node in list(self._mesh_items.values()) + list(self._walkmesh_items.values())
            if id(node) not in selected
        ]
        self._set_meshes_hidden(nodes, True)

    def _unhide_all_module_meshes(self) -> None:
        self._set_meshes_hidden(list(self._mesh_items.values()) + list(self._walkmesh_items.values()), False)

    def _create_selection_set_from_panel(self) -> None:
        nodes = self._selected_module_meshes()
        if not nodes or self._current_model is None:
            return
        name, ok = QtWidgets.QInputDialog.getText(self, "Selection Set", "Name:")
        if not ok or not name.strip():
            return
        sets = getattr(self._current_model, "_gr_selection_sets", None)
        if sets is None:
            sets = {}
            setattr(self._current_model, "_gr_selection_sets", sets)
        sets[name.strip()] = [self._mesh_label(node) for node in nodes]

    def _create_mesh_group_from_panel(self) -> None:
        nodes = self._selected_module_meshes()
        if not nodes or self._current_model is None:
            return
        name, ok = QtWidgets.QInputDialog.getText(self, "Mesh Group", "Name:")
        if not ok or not name.strip():
            return
        group_name = name.strip()
        groups = getattr(self._current_model, "_gr_mesh_groups", None)
        if groups is None:
            groups = {}
            setattr(self._current_model, "_gr_mesh_groups", groups)
        groups[group_name] = [self._mesh_label(node) for node in nodes]
        for node in nodes:
            setattr(node, "_gr_mesh_group", group_name)
        self._refresh_module_mesh_rows()
