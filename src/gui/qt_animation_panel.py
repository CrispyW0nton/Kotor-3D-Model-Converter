"""Qt animation panels for GhostRigger."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets

from .qt_theme import C, heading


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

    def load_model(self, model) -> None:
        self.listbox.clear()
        animations = getattr(model, "animations", []) or [] if model else []
        for anim in animations:
            self.listbox.addItem(getattr(anim, "name", str(anim)))
        self.info.setPlainText(f"{len(animations)} animation(s)")

    def selected_animation(self) -> str:
        item = self.listbox.currentItem()
        return item.text() if item else ""

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


class QtAnimationRetargetPanel(QtWidgets.QWidget):
    sourceCurrentRequested = QtCore.Signal()
    targetCurrentRequested = QtCore.Signal()
    sourceLibraryRequested = QtCore.Signal()
    targetLibraryRequested = QtCore.Signal()
    previewRequested = QtCore.Signal(str)
    applyRequested = QtCore.Signal(str)
    stopRequested = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._source_model = None
        self._target_model = None
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
            ("Preview", self._preview),
            ("Apply", self._apply),
            ("Stop", self.stopRequested.emit),
        ):
            button = QtWidgets.QPushButton(label)
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
        self.anim_list.itemDoubleClicked.connect(lambda _item: self._preview())
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
        button_row = QtWidgets.QHBoxLayout()
        current_button = QtWidgets.QPushButton("Use Current")
        library_button = QtWidgets.QPushButton(f"Select {title} from Library")
        if title == "Source":
            self.source_label = label
            current_button.clicked.connect(self.sourceCurrentRequested.emit)
            library_button.clicked.connect(self.sourceLibraryRequested.emit)
        else:
            self.target_label = label
            current_button.clicked.connect(self.targetCurrentRequested.emit)
            library_button.clicked.connect(self.targetLibraryRequested.emit)
        button_row.addWidget(current_button, 1)
        button_row.addWidget(library_button, 1)
        layout.addWidget(label)
        layout.addLayout(button_row)
        return box

    def set_source_model(self, model) -> None:
        self._source_model = model
        self.source_label.setText(self._model_label(model))
        self.anim_list.clear()
        for anim in getattr(model, "animations", []) or [] if model else []:
            self.anim_list.addItem(str(getattr(anim, "name", anim)))
        self._update_info()

    def set_target_model(self, model) -> None:
        self._target_model = model
        self.target_label.setText(self._model_label(model))
        self._update_info()

    def set_mapping_report(self, report) -> None:
        self.mapping.clear()
        for src, dst in sorted((getattr(report, "mapping", {}) or {}).items()):
            self.mapping.addTopLevelItem(QtWidgets.QTreeWidgetItem([src, dst]))
        self.mapping.resizeColumnToContents(0)
        self.info.setPlainText(
            f"Mapped bones: {getattr(report, 'matched_count', 0)}\n"
            f"Exact: {getattr(report, 'exact_matches', 0)}  Alias: {getattr(report, 'alias_matches', 0)}\n"
            f"Unmapped source: {len(getattr(report, 'missing_source', []) or [])}\n"
            f"Unmapped target: {len(getattr(report, 'missing_target', []) or [])}"
        )

    def selected_animation(self) -> str:
        item = self.anim_list.currentItem()
        return item.text() if item else ""

    def config_kwargs(self) -> dict:
        return {
            "preserve_model_scale": self.preserve_scale.isChecked(),
            "ignore_scale_keys": self.ignore_scale.isChecked(),
            "copy_material_animation": self.material_keys.isChecked(),
        }

    def _preview(self) -> None:
        self.previewRequested.emit(self.selected_animation())

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
