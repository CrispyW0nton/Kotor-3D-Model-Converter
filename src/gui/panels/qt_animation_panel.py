"""Qt animation panels for GhostRigger."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets

from src.gui.qt_lib.assets.qt_theme import C, heading


class QtAnimationsPanel(QtWidgets.QWidget):
    animationSelected = QtCore.Signal(str)
    animationActionRequested = QtCore.Signal(str, str)
    seekRequested = QtCore.Signal(int)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.addWidget(heading("Animations"))
        self.listbox = QtWidgets.QListWidget()
        self.listbox.currentTextChanged.connect(self.animationSelected.emit)
        self.listbox.itemDoubleClicked.connect(lambda _item: self._emit_action("Play"))
        root.addWidget(self.listbox, 1)
        self.info = QtWidgets.QPlainTextEdit()
        self.info.setReadOnly(True)
        self.info.setMaximumHeight(90)
        root.addWidget(self.info)
        self.seek = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.seek.setRange(0, 100)
        self.seek.valueChanged.connect(self.seekRequested.emit)
        root.addWidget(self.seek)
        controls = QtWidgets.QHBoxLayout()
        for label in ("Play", "Stop", "Loop", "Export"):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, text=label: self._emit_action(text))
            controls.addWidget(button)
        root.addLayout(controls)
        output_controls = QtWidgets.QHBoxLayout()
        for label in ("Bake Animation", "Export Binary MDL"):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, text=label: self._emit_action(text))
            output_controls.addWidget(button)
        root.addLayout(output_controls)

    def load_model(self, model, select_name: str = "") -> None:
        self.listbox.clear()
        animations = getattr(model, "animations", []) or [] if model else []
        for anim in animations:
            self.listbox.addItem(getattr(anim, "name", str(anim)))
        if select_name:
            self.select_animation(select_name)
        self.info.setPlainText(f"{len(animations)} animation(s)")

    def selected_animation(self) -> str:
        item = self.listbox.currentItem()
        return item.text() if item else ""

    def select_animation(self, anim_name: str) -> bool:
        if not anim_name:
            return False
        matches = self.listbox.findItems(anim_name, QtCore.Qt.MatchExactly)
        if not matches:
            return False
        self.listbox.setCurrentItem(matches[0])
        self.listbox.scrollToItem(matches[0])
        return True

    def _emit_action(self, action: str) -> None:
        self.animationActionRequested.emit(action, self.selected_animation())


class QtAnimationLibraryPanel(QtWidgets.QWidget):
    libraryActionRequested = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.addWidget(heading("Animation Library"))
        scan = QtWidgets.QHBoxLayout()
        for label in ("Scan Animations", "Refresh"):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, text=label: self.libraryActionRequested.emit(text))
            scan.addWidget(button)
        root.addLayout(scan)
        self.filter_edit = QtWidgets.QLineEdit()
        self.filter_edit.setPlaceholderText("Filter animations")
        root.addWidget(self.filter_edit)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Model", "Animation", "Frames", "Source"])
        root.addWidget(self.tree, 1)
        actions = QtWidgets.QHBoxLayout()
        for label in ("Load", "Preview", "Export"):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, text=label: self.libraryActionRequested.emit(text))
            actions.addWidget(button)
        root.addLayout(actions)

    def set_entries(self, entries: list[dict]) -> None:
        self.tree.clear()
        for entry in entries:
            item = QtWidgets.QTreeWidgetItem([
                str(entry.get("model", "")),
                str(entry.get("animation", "")),
                str(entry.get("frames", "")),
                str(entry.get("source", "")),
            ])
            item.setData(0, QtCore.Qt.UserRole, entry)
            self.tree.addTopLevelItem(item)

    def selected_entry(self) -> Optional[dict]:
        item = self.tree.currentItem()
        return item.data(0, QtCore.Qt.UserRole) if item else None


class QtAnimationLibraryCombinedPanel(QtWidgets.QWidget):
    """Combined right-pane host for current-model animations and the library."""

    def __init__(
        self,
        animations_panel: QtAnimationsPanel,
        library_panel: QtAnimationLibraryPanel,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self.animations_panel = animations_panel
        self.library_panel = library_panel
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self.animations_panel, "Current")
        self.tabs.addTab(self.library_panel, "Library")
        root.addWidget(self.tabs, 1)

    def show_current_model_tab(self) -> None:
        self.tabs.setCurrentWidget(self.animations_panel)

    def show_library_tab(self) -> None:
        self.tabs.setCurrentWidget(self.library_panel)


class QtAnimationRetargetPanel(QtWidgets.QWidget):
    sourceCurrentRequested = QtCore.Signal()
    targetCurrentRequested = QtCore.Signal()
    sourceLibraryRequested = QtCore.Signal()
    targetLibraryRequested = QtCore.Signal()
    sourceGameLibraryRequested = QtCore.Signal(dict)
    targetGameLibraryRequested = QtCore.Signal(dict)
    sourceExternalImportRequested = QtCore.Signal()
    targetExternalImportRequested = QtCore.Signal()
    previewRequested = QtCore.Signal(str)
    applyRequested = QtCore.Signal(str)
    stopRequested = QtCore.Signal()
    animationSelected = QtCore.Signal(str)
    sourceAnimationPlayRequested = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._source_model = None
        self._target_model = None
        self._library_rows: list[dict] = []
        self._manual_mapping: dict[str, str] = {}
        self._updating_mapping = False
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        self.source_box = self._make_model_box("Source")
        self.target_box = self._make_model_box("Target")

        content = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        content.setChildrenCollapsible(False)
        content.addWidget(self._make_animation_column())
        content.addWidget(self._make_mapping_column())
        content.setSizes([320, 520])
        root.addWidget(content, 1)

        controls = QtWidgets.QHBoxLayout()
        controls.setSpacing(6)
        for label, slot in (
            ("Retarget", self._preview),
            ("Apply", self._apply),
            ("Stop", self.stopRequested.emit),
        ):
            button = QtWidgets.QPushButton(label)
            if label == "Retarget":
                button.setObjectName("retargetSelectedAnimationButton")
            button.clicked.connect(slot)
            controls.addWidget(button, 1)
        root.addLayout(controls)

    def _make_animation_column(self) -> QtWidgets.QWidget:
        column = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(heading("Animations"))
        self.anim_list = QtWidgets.QListWidget()
        self.anim_list.currentTextChanged.connect(self.animationSelected.emit)
        self.anim_list.itemDoubleClicked.connect(lambda _item: self._play_source_animation())
        layout.addWidget(self.anim_list, 1)
        return column

    def _make_mapping_column(self) -> QtWidgets.QWidget:
        column = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        mapping_box = QtWidgets.QGroupBox("Source Bone / Target Bone")
        mapping_layout = QtWidgets.QVBoxLayout(mapping_box)
        mapping_layout.setContentsMargins(6, 6, 6, 6)
        self.mapping = QtWidgets.QTreeWidget()
        self.mapping.setHeaderLabels(["Source Bone", "Target Bone"])
        mapping_layout.addWidget(self.mapping, 1)
        layout.addWidget(mapping_box, 3)

        info_box = QtWidgets.QGroupBox("Information")
        info_layout = QtWidgets.QVBoxLayout(info_box)
        info_layout.setContentsMargins(6, 6, 6, 6)
        self.info = QtWidgets.QPlainTextEdit()
        self.info.setReadOnly(True)
        self.info.setMinimumHeight(82)
        info_layout.addWidget(self.info)
        layout.addWidget(info_box, 1)

        options = QtWidgets.QGroupBox("Transfer")
        opt_layout = QtWidgets.QVBoxLayout(options)
        opt_layout.setContentsMargins(6, 6, 6, 6)
        self.preserve_scale = QtWidgets.QCheckBox("Preserve target size")
        self.preserve_scale.setChecked(True)
        self.ignore_scale = QtWidgets.QCheckBox("Ignore scale keys")
        self.ignore_scale.setChecked(True)
        self.material_keys = QtWidgets.QCheckBox("Copy material animation")
        self.material_keys.setChecked(True)
        for box in (self.preserve_scale, self.ignore_scale, self.material_keys):
            opt_layout.addWidget(box)
        layout.addWidget(options, 0)
        return column

    def _make_model_box(self, title: str) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        label = QtWidgets.QLabel("None")
        label.setWordWrap(True)
        library_combo = QtWidgets.QComboBox()
        library_combo.setEditable(True)
        library_combo.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        library_combo.setMinimumWidth(240)
        library_combo.setPlaceholderText(f"Search {title.lower()} game-library model")
        library_combo.lineEdit().setPlaceholderText(f"Search {title.lower()} game-library model")
        completer = QtWidgets.QCompleter(library_combo.model(), library_combo)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchContains)
        library_combo.setCompleter(completer)
        button_row = QtWidgets.QHBoxLayout()
        current_button = QtWidgets.QPushButton("Use Current")
        library_button = QtWidgets.QPushButton("Load from Game Library")
        external_button = QtWidgets.QPushButton("Import External File...")
        if title == "Source":
            self.source_label = label
            self.source_library_combo = library_combo
            current_button.clicked.connect(self.sourceCurrentRequested.emit)
            library_button.clicked.connect(lambda _checked=False: self._emit_or_request_library_row("source"))
            external_button.clicked.connect(self.sourceExternalImportRequested.emit)
            library_combo.activated.connect(lambda _index=0: self._emit_library_row("source"))
        else:
            self.target_label = label
            self.target_library_combo = library_combo
            current_button.clicked.connect(self.targetCurrentRequested.emit)
            library_button.clicked.connect(lambda _checked=False: self._emit_or_request_library_row("target"))
            external_button.clicked.connect(self.targetExternalImportRequested.emit)
            library_combo.activated.connect(lambda _index=0: self._emit_library_row("target"))
        button_row.addWidget(current_button, 1)
        button_row.addWidget(library_button, 1)
        button_row.addWidget(external_button, 1)
        layout.addWidget(label)
        layout.addWidget(library_combo)
        layout.addLayout(button_row)
        return box

    def set_library_rows(self, rows: list[dict]) -> None:
        self._library_rows = [dict(row) for row in rows or []]
        for combo in (getattr(self, "source_library_combo", None), getattr(self, "target_library_combo", None)):
            if combo is not None:
                self._populate_library_combo(combo)

    def selected_library_row(self, role: str) -> Optional[dict]:
        combo = self.source_library_combo if role == "source" else self.target_library_combo
        row = combo.currentData()
        if isinstance(row, dict):
            return dict(row)
        text = combo.currentText().strip().lower()
        if not text:
            return None
        for candidate in self._library_rows:
            if text in self._library_row_label(candidate).lower():
                return dict(candidate)
        return None

    def _populate_library_combo(self, combo: QtWidgets.QComboBox) -> None:
        current = combo.currentText()
        combo.blockSignals(True)
        try:
            combo.clear()
            combo.addItem("Search game library...", None)
            for row in self._library_rows:
                combo.addItem(self._library_row_label(row), dict(row))
            if current:
                combo.setCurrentText(current)
        finally:
            combo.blockSignals(False)

    def _emit_library_row(self, role: str) -> None:
        row = self.selected_library_row(role)
        if not row:
            return
        if role == "source":
            self.sourceGameLibraryRequested.emit(row)
        else:
            self.targetGameLibraryRequested.emit(row)

    def _emit_or_request_library_row(self, role: str) -> None:
        row = self.selected_library_row(role)
        if row:
            if role == "source":
                self.sourceGameLibraryRequested.emit(row)
            else:
                self.targetGameLibraryRequested.emit(row)
            return
        if role == "source":
            self.sourceLibraryRequested.emit()
        else:
            self.targetLibraryRequested.emit()

    def _library_row_label(self, row: dict) -> str:
        game = str(row.get("game") or "").strip()
        resref = str(row.get("resref") or row.get("name") or "").strip()
        category = str(row.get("category") or "").strip()
        module = str(row.get("module_code") or row.get("area_label") or "").strip()
        pieces = [piece for piece in (game, resref, category, module) if piece]
        return " : ".join(pieces) if pieces else "(unnamed model)"

    def set_source_model(self, model) -> None:
        self._source_model = model
        self._manual_mapping.clear()
        self.source_label.setText(self._model_label(model))
        self.anim_list.clear()
        for anim in getattr(model, "animations", []) or [] if model else []:
            item = QtWidgets.QListWidgetItem(str(getattr(anim, "name", anim)))
            length = float(getattr(anim, "length", 0.0) or 0.0)
            if length > 0.0:
                item.setToolTip(f"{length:.3f}s")
            item.setData(QtCore.Qt.UserRole, anim)
            self.anim_list.addItem(item)
        if self.anim_list.count() == 1:
            self.anim_list.setCurrentRow(0)
        self._update_info()

    def set_target_model(self, model) -> None:
        self._target_model = model
        self._manual_mapping.clear()
        self.target_label.setText(self._model_label(model))
        self._update_info()

    def set_mapping_report(self, report) -> None:
        self._updating_mapping = True
        self.mapping.clear()
        target_names = self._bone_names(self._target_model)
        mapped = dict(getattr(report, "mapping", {}) or {})
        missing = {str(src or "").lower() for src in (getattr(report, "missing_source", []) or [])}
        for src in sorted(set(mapped).union(missing)):
            auto_dst = mapped.get(src, "")
            current_dst = self._manual_mapping.get(src, auto_dst)
            item = QtWidgets.QTreeWidgetItem([src, ""])
            item.setData(0, QtCore.Qt.UserRole, src)
            item.setData(1, QtCore.Qt.UserRole, auto_dst)
            self.mapping.addTopLevelItem(item)
            combo = QtWidgets.QComboBox(self.mapping)
            combo.setEditable(False)
            combo.addItem("")
            for name in target_names:
                combo.addItem(name)
            if current_dst and combo.findText(current_dst) < 0:
                combo.addItem(current_dst)
            combo.setCurrentText(current_dst)
            combo.currentTextChanged.connect(
                lambda text, src_key=src, auto_key=auto_dst: self._on_mapping_combo_changed(src_key, auto_key, text)
            )
            self.mapping.setItemWidget(item, 1, combo)
        self._updating_mapping = False
        self.mapping.resizeColumnToContents(0)
        self.info.setPlainText(
            f"Mapped bones: {getattr(report, 'matched_count', 0)}\n"
            f"Exact: {getattr(report, 'exact_matches', 0)}  Alias: {getattr(report, 'alias_matches', 0)}  "
            f"Manual: {getattr(report, 'manual_matches', 0)}\n"
            f"Unmapped source: {len(getattr(report, 'missing_source', []) or [])}\n"
            f"Unmapped target: {len(getattr(report, 'missing_target', []) or [])}"
        )

    def selected_animation(self) -> str:
        item = self.anim_list.currentItem()
        return item.text() if item else ""

    def select_animation(self, anim_name: str) -> bool:
        if not anim_name:
            return False
        matches = self.anim_list.findItems(anim_name, QtCore.Qt.MatchExactly)
        if not matches:
            return False
        self.anim_list.setCurrentItem(matches[0])
        self.anim_list.scrollToItem(matches[0])
        return True

    def config_kwargs(self) -> dict:
        return {
            "preserve_model_scale": self.preserve_scale.isChecked(),
            "ignore_scale_keys": self.ignore_scale.isChecked(),
            "copy_material_animation": self.material_keys.isChecked(),
        }

    def manual_bone_mapping(self) -> dict[str, str]:
        return dict(self._manual_mapping)

    def _on_mapping_combo_changed(self, src_key: str, auto_key: str, text: str) -> None:
        if self._updating_mapping:
            return
        dst_key = str(text or "").strip().lower()
        if not dst_key or dst_key == str(auto_key or "").lower():
            self._manual_mapping.pop(src_key, None)
        else:
            self._manual_mapping[src_key] = dst_key

    def _bone_names(self, model) -> list[str]:
        if model is None or not hasattr(model, "all_nodes"):
            return []
        names = []
        for node in model.all_nodes():
            name = str(getattr(node, "name", "") or "").strip().lower()
            if name:
                names.append(name)
        return sorted(set(names))

    def _preview(self) -> None:
        self.previewRequested.emit(self.selected_animation())

    def _play_source_animation(self) -> None:
        self.sourceAnimationPlayRequested.emit(self.selected_animation())

    def _apply(self) -> None:
        self.applyRequested.emit(self.selected_animation())

    def _model_label(self, model) -> str:
        if model is None:
            return "None"
        return (
            f"{getattr(model, 'name', '?')}\n"
            f"{len(getattr(model, 'animations', []) or [])} anims  "
            f"{len(list(model.all_nodes())) if hasattr(model, 'all_nodes') else 0} nodes"
        )

    def _update_info(self) -> None:
        if self._source_model is None or self._target_model is None:
            self.info.setPlainText("Set a source model with animations and a target model.")
