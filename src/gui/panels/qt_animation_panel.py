"""Qt animation panels for GhostRigger."""

from __future__ import annotations

import re
from typing import Optional

from PySide6 import QtCore, QtWidgets

from src.core.retargeting.retarget_output_naming import KotorOutputAnimationNameMode
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
    pauseRequested = QtCore.Signal()
    stopRequested = QtCore.Signal()
    animationSelected = QtCore.Signal(str)
    sourceAnimationPlayRequested = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._source_model = None
        self._target_model = None
        self._library_rows: list[dict] = []
        self._animation_assignments: dict[str, dict] = {}
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        self.source_box = self._make_model_box("Source")
        self.target_box = self._make_model_box("Target")
        self.animation_section = self._make_animation_column()
        self.info_section = self._make_information_section()
        self.transfer_section = self._make_transfer_section()
        self.assignment_section = self._make_assignment_column()

        content = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        content.setChildrenCollapsible(False)
        content.addWidget(self.animation_section)
        content.addWidget(self.assignment_section)
        content.setSizes([320, 520])
        root.addWidget(content, 1)

        self.controls_widget = self._make_controls_widget()
        root.addWidget(self.controls_widget)

    def _make_controls_widget(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        controls = QtWidgets.QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(6)
        for label, slot in (
            ("Play", self._play_source_animation),
            ("Pause", self.pauseRequested.emit),
            ("Stop", self.stopRequested.emit),
            ("Retarget", self._preview),
            ("Export MDL and Assign Retargeted Animations", self._apply),
        ):
            button = QtWidgets.QPushButton(label)
            if label == "Retarget":
                button.setObjectName("retargetSelectedAnimationButton")
            elif label == "Play":
                button.setObjectName("playSelectedRetargetAnimationButton")
            elif label == "Pause":
                button.setObjectName("pauseRetargetAnimationButton")
            elif label == "Stop":
                button.setObjectName("stopRetargetAnimationButton")
            elif label.startswith("Export MDL"):
                button.setObjectName("exportAssignedRetargetAnimationsButton")
            button.clicked.connect(slot)
            controls.addWidget(button, 1)
        widget.setLayout(controls)
        return widget

    def _make_animation_column(self) -> QtWidgets.QWidget:
        column = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(heading("Animations"))
        self.anim_list = QtWidgets.QListWidget()
        self.anim_list.currentItemChanged.connect(
            lambda item, _old=None: self.animationSelected.emit(self._source_name_for_item(item))
        )
        self.anim_list.itemDoubleClicked.connect(lambda _item: self._play_source_animation())
        self.anim_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.anim_list.customContextMenuRequested.connect(self._show_animation_context_menu)
        layout.addWidget(self.anim_list, 1)
        return column

    def _make_assignment_column(self) -> QtWidgets.QWidget:
        column = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.info_section, 1)
        layout.addWidget(self.transfer_section, 0)
        return column

    def _make_information_section(self) -> QtWidgets.QWidget:
        info_box = QtWidgets.QGroupBox("Information")
        info_layout = QtWidgets.QVBoxLayout(info_box)
        info_layout.setContentsMargins(6, 6, 6, 6)
        self.info = QtWidgets.QPlainTextEdit()
        self.info.setReadOnly(True)
        self.info.setMinimumHeight(82)
        info_layout.addWidget(self.info)
        return info_box

    def _make_transfer_section(self) -> QtWidgets.QWidget:
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
        opt_layout.addStretch(1)
        return options

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
        self.source_label.setText(self._model_label(model))
        previous_assignments = {str(key): dict(value) for key, value in self._animation_assignments.items()}
        self.anim_list.clear()
        self._animation_assignments.clear()
        for anim in getattr(model, "animations", []) or [] if model else []:
            source_name = str(getattr(anim, "name", anim))
            item = QtWidgets.QListWidgetItem()
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked)
            length = float(getattr(anim, "length", 0.0) or 0.0)
            item.setData(QtCore.Qt.UserRole, anim)
            item.setData(QtCore.Qt.UserRole + 2, source_name)
            assignment = previous_assignments.get(source_name) or self._default_assignment_for(source_name)
            item.setData(QtCore.Qt.UserRole + 1, assignment)
            self._animation_assignments[source_name] = dict(assignment)
            self._render_animation_item(item, length=length)
            self.anim_list.addItem(item)
        if self.anim_list.count() == 1:
            self.anim_list.setCurrentRow(0)
        self._update_info()

    def set_target_model(self, model) -> None:
        self._target_model = model
        self.target_label.setText(self._model_label(model))
        self._update_info()

    def set_mapping_report(self, report) -> None:
        self.info.setPlainText(
            f"Mapped bones: {getattr(report, 'matched_count', 0)}\n"
            f"Exact: {getattr(report, 'exact_matches', 0)}  Alias: {getattr(report, 'alias_matches', 0)}  "
            f"Manual: {getattr(report, 'manual_matches', 0)}\n"
            f"Unmapped source: {len(getattr(report, 'missing_source', []) or [])}\n"
            f"Unmapped target: {len(getattr(report, 'missing_target', []) or [])}"
        )

    def selected_animation(self) -> str:
        item = self.anim_list.currentItem()
        return self._source_name_for_item(item)

    def select_animation(self, anim_name: str) -> bool:
        if not anim_name:
            return False
        for index in range(self.anim_list.count()):
            item = self.anim_list.item(index)
            if self._source_name_for_item(item) == str(anim_name):
                self.anim_list.setCurrentItem(item)
                self.anim_list.scrollToItem(item)
                return True
        return False

    def config_kwargs(self) -> dict:
        return {
            "preserve_model_scale": self.preserve_scale.isChecked(),
            "ignore_scale_keys": self.ignore_scale.isChecked(),
            "copy_material_animation": self.material_keys.isChecked(),
        }

    def manual_bone_mapping(self) -> dict[str, str]:
        return {}

    def assignment_for_animation(self, anim_name: str | None = None) -> dict:
        item = self._item_for_animation(anim_name or self.selected_animation())
        if item is None:
            return {}
        source_name = self._source_name_for_item(item)
        assignment = item.data(QtCore.Qt.UserRole + 1)
        if not isinstance(assignment, dict):
            assignment = self._default_assignment_for(source_name)
            item.setData(QtCore.Qt.UserRole + 1, assignment)
        result = dict(assignment)
        result.setdefault("source_animation", source_name)
        result["checked"] = item.checkState() == QtCore.Qt.Checked
        return result

    def checked_animation_assignments(self) -> list[dict]:
        assignments: list[dict] = []
        for index in range(self.anim_list.count()):
            item = self.anim_list.item(index)
            if item.checkState() == QtCore.Qt.Checked:
                assignments.append(self.assignment_for_animation(self._source_name_for_item(item)))
        return assignments

    def set_animation_assignment(
        self,
        anim_name: str,
        *,
        output_name: str | None = None,
        output_mode: KotorOutputAnimationNameMode | str | None = None,
        checked: bool | None = None,
    ) -> None:
        item = self._item_for_animation(anim_name)
        if item is None:
            return
        source_name = self._source_name_for_item(item)
        assignment = self.assignment_for_animation(source_name) or self._default_assignment_for(source_name)
        if output_name is not None:
            assignment["output_name"] = str(output_name or "").strip()
        if output_mode is not None:
            assignment["output_mode"] = self._coerce_output_mode(output_mode).value
        if checked is not None:
            item.setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
        item.setData(QtCore.Qt.UserRole + 1, dict(assignment))
        self._animation_assignments[source_name] = dict(assignment)
        self._render_animation_item(item)

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

    def _item_for_animation(self, anim_name: str | None) -> QtWidgets.QListWidgetItem | None:
        needle = str(anim_name or "")
        if not needle:
            return self.anim_list.currentItem()
        for index in range(self.anim_list.count()):
            item = self.anim_list.item(index)
            if self._source_name_for_item(item) == needle:
                return item
        return None

    def _source_name_for_item(self, item: QtWidgets.QListWidgetItem | None) -> str:
        if item is None:
            return ""
        source_name = item.data(QtCore.Qt.UserRole + 2)
        return str(source_name or item.text() or "")

    def _default_assignment_for(self, source_name: str) -> dict:
        return {
            "source_animation": source_name,
            "output_name": self._safe_custom_output_name(source_name),
            "output_mode": KotorOutputAnimationNameMode.CUSTOM_PATCH.value,
            "checked": True,
        }

    def _render_animation_item(self, item: QtWidgets.QListWidgetItem, *, length: float | None = None) -> None:
        source_name = self._source_name_for_item(item)
        assignment = item.data(QtCore.Qt.UserRole + 1)
        if not isinstance(assignment, dict):
            assignment = self._default_assignment_for(source_name)
        mode = self._coerce_output_mode(assignment.get("output_mode"))
        output_name = str(assignment.get("output_name") or "").strip() or self._safe_custom_output_name(source_name)
        mode_label = "custom patch" if mode == KotorOutputAnimationNameMode.CUSTOM_PATCH else "vanilla slot"
        item.setText(f"{source_name}  ->  {output_name} ({mode_label})")
        tooltip = (
            f"Source animation: {source_name}\n"
            f"Target output animation: {output_name}\n"
            f"Output type: {mode_label}"
        )
        if length is not None and length > 0.0:
            tooltip += f"\nLength: {length:.3f}s"
        item.setToolTip(tooltip)

    def _show_animation_context_menu(self, pos: QtCore.QPoint) -> None:
        item = self.anim_list.itemAt(pos)
        if item is None:
            return
        self.anim_list.setCurrentItem(item)
        menu = QtWidgets.QMenu(self)
        rename_action = menu.addAction("Rename target output animation...")
        custom_action = menu.addAction("Set output type: Custom animation patch")
        vanilla_action = menu.addAction("Set output type: Vanilla slot override")
        toggle_action = menu.addAction("Assign/export this animation")
        toggle_action.setCheckable(True)
        toggle_action.setChecked(item.checkState() == QtCore.Qt.Checked)
        chosen = menu.exec(self.anim_list.mapToGlobal(pos))
        if chosen is None:
            return
        source_name = self._source_name_for_item(item)
        if chosen is rename_action:
            current = str(self.assignment_for_animation(source_name).get("output_name") or "")
            text, accepted = QtWidgets.QInputDialog.getText(
                self,
                "Rename Retarget Output",
                "Target output animation name:",
                QtWidgets.QLineEdit.Normal,
                current,
            )
            if accepted:
                self.set_animation_assignment(source_name, output_name=text)
        elif chosen is custom_action:
            self.set_animation_assignment(source_name, output_mode=KotorOutputAnimationNameMode.CUSTOM_PATCH)
        elif chosen is vanilla_action:
            self.set_animation_assignment(source_name, output_mode=KotorOutputAnimationNameMode.VANILLA_SLOT)
        elif chosen is toggle_action:
            self.set_animation_assignment(source_name, checked=toggle_action.isChecked())

    def _coerce_output_mode(self, value) -> KotorOutputAnimationNameMode:
        if isinstance(value, KotorOutputAnimationNameMode):
            return value
        raw = str(value or "").strip().lower()
        if raw in {KotorOutputAnimationNameMode.VANILLA_SLOT.value, "vanilla", "slot"}:
            return KotorOutputAnimationNameMode.VANILLA_SLOT
        return KotorOutputAnimationNameMode.CUSTOM_PATCH

    def _safe_custom_output_name(self, source_name: str) -> str:
        text = re.sub(r"[^A-Za-z0-9_-]+", "_", str(source_name or "").strip())
        text = re.sub(r"_+", "_", text).strip("_-")
        if not text:
            text = "retargeted_animation"
        return text[:64]

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
