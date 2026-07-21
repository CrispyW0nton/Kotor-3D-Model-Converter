"""Particle Editor window.

Standalone workspace for KOTOR emitter particle systems:

- loads any game model into an embedded main-viewport preview and lists its
  emitter nodes,
- live-edits every emitter header field and controller channel through
  :class:`src.core.particles.EmitterDefinition` (edits restart the emitter's
  simulation in the ModernGL particle pass immediately),
- scans both installed game libraries for every retail emitter and exposes
  them as templates that can be applied to an existing emitter or added to
  the model as a brand-new emitter node.

Owned by ``GhostRigger.Core.Tools`` (product tool orchestration); simulation,
definitions, and library scanning live in ``src.core.particles``.
"""

from __future__ import annotations

import gc
import threading
import time as time_module
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.particles.emitter_data import (
    BLEND_MODES,
    EmitterDefinition,
    EmitterFlags,
    ForceField,
    RENDER_MODES,
    UPDATE_MODES,
    emitter_nodes,
)
from src.core.particles.emitter_library import (
    EmitterTemplate,
    library_cache_path,
    load_library,
    save_library,
    scan_resource_manager_library,
)

_GAMES = ("K1", "K2")

# (channel, label, minimum, maximum, step, decimals)
_SCALAR_SPECS: Dict[str, List[tuple]] = {
    "Emission": [
        ("birthrate", "Birthrate (particles/s)", 0.0, 4096.0, 1.0, 2),
        ("randombirthrate", "Random Birthrate", 0.0, 4096.0, 1.0, 2),
        ("lifeexp", "Life Expectancy (s)", 0.0, 300.0, 0.1, 3),
        ("velocity", "Velocity", -100.0, 100.0, 0.05, 3),
        ("randvel", "Random Velocity", 0.0, 100.0, 0.05, 3),
        ("spread", "Spread (deg or rad)", 0.0, 360.0, 1.0, 3),
        ("xsize", "Emitter Size X", 0.0, 100.0, 0.1, 3),
        ("ysize", "Emitter Size Y", 0.0, 100.0, 0.1, 3),
        ("threshold", "Threshold", -100.0, 100.0, 0.1, 3),
    ],
    "Physics": [
        ("grav", "Gravity", -100.0, 100.0, 0.05, 3),
        ("drag", "Drag", 0.0, 100.0, 0.05, 3),
        ("mass", "Mass", -100.0, 100.0, 0.1, 3),
        ("particlerot", "Particle Rotation (rev/s)", -50.0, 50.0, 0.01, 3),
        ("bounce_co", "Bounce Coefficient", 0.0, 10.0, 0.05, 3),
        ("blurlength", "Blur Length", 0.0, 100.0, 0.5, 2),
    ],
    "Over Lifetime": [
        ("alphastart", "Alpha Start", 0.0, 1.0, 0.05, 3),
        ("alphamid", "Alpha Mid", 0.0, 1.0, 0.05, 3),
        ("alphaend", "Alpha End", 0.0, 1.0, 0.05, 3),
        ("sizestart", "Size Start", 0.0, 100.0, 0.05, 3),
        ("sizemid", "Size Mid", 0.0, 100.0, 0.05, 3),
        ("sizeend", "Size End", 0.0, 100.0, 0.05, 3),
        ("sizestart_y", "Size Start Y", 0.0, 100.0, 0.05, 3),
        ("sizemid_y", "Size Mid Y", 0.0, 100.0, 0.05, 3),
        ("sizeend_y", "Size End Y", 0.0, 100.0, 0.05, 3),
        ("percentstart", "Percent Start", 0.0, 1.0, 0.05, 3),
        ("percentmid", "Percent Mid", 0.0, 1.0, 0.05, 3),
        ("percentend", "Percent End", 0.0, 1.0, 0.05, 3),
    ],
    "Flipbook Frames": [
        ("fps", "FPS", 0.0, 240.0, 1.0, 2),
        ("framestart", "Frame Start", 0.0, 1024.0, 1.0, 0),
        ("frameend", "Frame End", 0.0, 1024.0, 1.0, 0),
    ],
    "Advanced": [
        ("combinetime", "Combine Time", 0.0, 100.0, 0.1, 3),
        ("targetsize", "Target Size", 0.0, 1024.0, 1.0, 2),
        ("tangentspread", "Tangent Spread", 0.0, 360.0, 1.0, 2),
        ("tangentlength", "Tangent Length", 0.0, 100.0, 0.1, 3),
        ("numcontrolpts", "Control Points", 0.0, 32.0, 1.0, 0),
        ("controlptradius", "Control Point Radius", 0.0, 100.0, 0.1, 3),
        ("controlptdelay", "Control Point Delay", 0.0, 100.0, 0.1, 3),
        ("p2p_bezier2", "P2P Bezier 2", -100.0, 100.0, 0.05, 3),
        ("p2p_bezier3", "P2P Bezier 3", -100.0, 100.0, 0.05, 3),
        ("lightningdelay", "Lightning Delay", 0.0, 100.0, 0.1, 3),
        ("lightningradius", "Lightning Radius", 0.0, 100.0, 0.1, 3),
        ("lightningscale", "Lightning Scale", 0.0, 100.0, 0.1, 3),
        ("lightningsubdiv", "Lightning Subdivisions", 0.0, 64.0, 1.0, 0),
        ("lightningzigzag", "Lightning Zigzag", 0.0, 100.0, 0.1, 3),
    ],
}

_COLOR_SPECS = [
    ("colorstart", "Color Start"),
    ("colormid", "Color Mid"),
    ("colorend", "Color End"),
]

_FLAG_SPECS = [
    (EmitterFlags.P2P, "Point to Point"),
    (EmitterFlags.P2P_SEL, "P2P Select"),
    (EmitterFlags.AFFECTED_BY_WIND, "Affected by Wind"),
    (EmitterFlags.TINTED, "Tinted"),
    (EmitterFlags.BOUNCE, "Bounce"),
    (EmitterFlags.RANDOM, "Random"),
    (EmitterFlags.INHERIT, "Inherit"),
    (EmitterFlags.INHERIT_VEL, "Inherit Velocity"),
    (EmitterFlags.INHERIT_LOCAL, "Inherit Local"),
    (EmitterFlags.SPLAT, "Splat"),
    (EmitterFlags.INHERIT_PART, "Inherit Particle"),
    (EmitterFlags.DEPTH_TEXTURE, "Depth Texture"),
]


class QtParticleEditorWindow(QtWidgets.QMainWindow):
    """Particle editing workspace with live viewport preview."""

    scanProgress = QtCore.Signal(str, int, int)
    scanFinished = QtCore.Signal(str, int)
    workerDone = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, *,
                 resource_manager=None, settings_data: Optional[dict] = None,
                 app_root: Optional[Path] = None):
        super().__init__(parent)
        self.setObjectName("ParticleEditorWindow")
        self.setWindowTitle("Particle Editor — KOTOR Emitters")
        self.resize(1480, 900)

        self._resource_manager = resource_manager
        self._settings_data = dict(settings_data or {})
        self._app_root = Path(app_root or Path.cwd())
        self._model = None
        self._model_game = "K1"
        self._selected_node = None
        self._definition: Optional[EmitterDefinition] = None
        self._updating_widgets = False
        self._templates: Dict[str, List[EmitterTemplate]] = {"K1": [], "K2": []}
        self._scan_thread: Optional[threading.Thread] = None
        self._scan_cancel = threading.Event()

        self._anim_engine = None
        self._anim_length = 0.0
        self._anim_timer = QtCore.QTimer(self)
        self._anim_timer.setInterval(33)
        self._anim_timer.timeout.connect(self._on_anim_tick)
        self._anim_wall = 0.0

        # PySide GC guard: while a library worker thread parses multi-megabyte
        # JSON or thousands of models, an automatic Python GC cycle can run on
        # that thread and finalize Qt wrapper objects off the GUI thread — an
        # instant access violation.  While any worker is active, automatic GC
        # stays disabled and this GUI-thread timer performs the collections.
        self._gc_guard_count = 0
        self._gc_guard_was_enabled = True
        self._gc_guard_timer = QtCore.QTimer(self)
        self._gc_guard_timer.setInterval(2000)
        self._gc_guard_timer.timeout.connect(lambda: gc.collect())

        self.scanProgress.connect(self._on_scan_progress)
        self.scanFinished.connect(self._on_scan_finished)
        self.workerDone.connect(self._end_gc_guard)

        self._build_ui()
        self._load_cached_libraries()

    # ── UI construction ──────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        toolbar = QtWidgets.QToolBar("Particle Editor Tools", self)
        toolbar.setObjectName("ParticleEditorToolbar")
        toolbar.setMovable(False)
        self.addToolBar(QtCore.Qt.TopToolBarArea, toolbar)

        toolbar.addWidget(QtWidgets.QLabel(" Game "))
        self.game_combo = QtWidgets.QComboBox()
        self.game_combo.addItems(list(_GAMES))
        toolbar.addWidget(self.game_combo)

        toolbar.addWidget(QtWidgets.QLabel(" Model "))
        self.resref_edit = QtWidgets.QLineEdit("plc_starmap")
        self.resref_edit.setMaximumWidth(180)
        self.resref_edit.returnPressed.connect(self._load_requested_model)
        toolbar.addWidget(self.resref_edit)

        load_action = toolbar.addAction("Load Model")
        load_action.triggered.connect(self._load_requested_model)
        from_main_action = toolbar.addAction("Use Main Window Model")
        from_main_action.triggered.connect(self._use_main_window_model)
        toolbar.addSeparator()

        toolbar.addWidget(QtWidgets.QLabel(" Animation "))
        self.anim_combo = QtWidgets.QComboBox()
        self.anim_combo.setMinimumWidth(140)
        toolbar.addWidget(self.anim_combo)
        play_action = toolbar.addAction("Play")
        play_action.triggered.connect(self._play_animation)
        stop_action = toolbar.addAction("Stop")
        stop_action.triggered.connect(self._stop_animation)
        toolbar.addSeparator()

        self.scan_action = toolbar.addAction("Scan Game Libraries")
        self.scan_action.triggered.connect(self._start_library_scan)
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setObjectName("ParticleEditorStatus")
        toolbar.addWidget(self.status_label)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        splitter.setObjectName("ParticleEditorSplitter")
        self.setCentralWidget(splitter)

        # Left: emitters + template library tree
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setObjectName("ParticleEditorTree")
        self.tree.setHeaderLabels(["Emitter", "Info"])
        self.tree.setColumnWidth(0, 220)
        self.tree.itemSelectionChanged.connect(self._on_tree_selection)
        self.tree.itemDoubleClicked.connect(self._on_tree_double_clicked)
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        splitter.addWidget(self.tree)

        self.model_group = QtWidgets.QTreeWidgetItem(["Model Emitters", ""])
        self.k1_group = QtWidgets.QTreeWidgetItem(["K1 Library", ""])
        self.k2_group = QtWidgets.QTreeWidgetItem(["K2 Library", ""])
        for item in (self.model_group, self.k1_group, self.k2_group):
            self.tree.addTopLevelItem(item)
        self.model_group.setExpanded(True)

        # Center: live preview viewport
        from src.core.rendering.renderer_settings import RendererSettings  # noqa: F401  (settings contract)
        from src.gui.qt_lib.viewports.qt_viewport import QtMainViewportWidget

        self.viewport = QtMainViewportWidget(self, map_studio_authoring_chrome=False)
        self.viewport.setObjectName("particleEditorPreviewViewport")
        set_settings = getattr(self.viewport, "set_renderer_settings", None)
        if callable(set_settings):
            set_settings(self._settings_data)
        splitter.addWidget(self.viewport)

        # Right: parameter editor
        panel = QtWidgets.QScrollArea()
        panel.setObjectName("ParticleEditorParamScroll")
        panel.setWidgetResizable(True)
        panel_body = QtWidgets.QWidget()
        panel.setWidget(panel_body)
        form_layout = QtWidgets.QVBoxLayout(panel_body)
        form_layout.setContentsMargins(8, 8, 8, 8)
        form_layout.setSpacing(6)
        splitter.addWidget(panel)
        splitter.setSizes([300, 780, 400])
        self._param_panel = panel

        self.selected_label = QtWidgets.QLabel("No emitter selected")
        self.selected_label.setObjectName("ParticleEditorSelectedLabel")
        form_layout.addWidget(self.selected_label)

        self._scalar_widgets: Dict[str, QtWidgets.QDoubleSpinBox] = {}
        self._color_buttons: Dict[str, QtWidgets.QPushButton] = {}
        self._flag_checks: Dict[int, QtWidgets.QCheckBox] = {}

        header_box = QtWidgets.QGroupBox("Emitter")
        header_form = QtWidgets.QFormLayout(header_box)
        self.update_combo = QtWidgets.QComboBox()
        self.update_combo.addItems(list(UPDATE_MODES))
        header_form.addRow("Update Mode", self.update_combo)
        self.render_combo = QtWidgets.QComboBox()
        self.render_combo.addItems(list(RENDER_MODES))
        header_form.addRow("Render Mode", self.render_combo)
        self.blend_combo = QtWidgets.QComboBox()
        self.blend_combo.addItems(list(BLEND_MODES))
        header_form.addRow("Blend", self.blend_combo)
        self.texture_edit = QtWidgets.QLineEdit()
        header_form.addRow("Texture", self.texture_edit)
        self.grid_x_spin = QtWidgets.QSpinBox()
        self.grid_x_spin.setRange(1, 64)
        header_form.addRow("Grid X", self.grid_x_spin)
        self.grid_y_spin = QtWidgets.QSpinBox()
        self.grid_y_spin.setRange(1, 64)
        header_form.addRow("Grid Y", self.grid_y_spin)
        self.loop_check = QtWidgets.QCheckBox("Loop")
        header_form.addRow("", self.loop_check)
        self.twosided_check = QtWidgets.QCheckBox("Two-Sided Texture")
        header_form.addRow("", self.twosided_check)
        self.frame_blend_check = QtWidgets.QCheckBox("Frame Blending")
        header_form.addRow("", self.frame_blend_check)
        self.render_order_spin = QtWidgets.QSpinBox()
        self.render_order_spin.setRange(0, 255)
        header_form.addRow("Render Order", self.render_order_spin)
        form_layout.addWidget(header_box)

        self.update_combo.currentTextChanged.connect(self._on_param_changed)
        self.render_combo.currentTextChanged.connect(self._on_param_changed)
        self.blend_combo.currentTextChanged.connect(self._on_param_changed)
        self.texture_edit.editingFinished.connect(self._on_param_changed)
        self.grid_x_spin.valueChanged.connect(self._on_param_changed)
        self.grid_y_spin.valueChanged.connect(self._on_param_changed)
        self.loop_check.toggled.connect(self._on_param_changed)
        self.twosided_check.toggled.connect(self._on_param_changed)
        self.frame_blend_check.toggled.connect(self._on_param_changed)
        self.render_order_spin.valueChanged.connect(self._on_param_changed)

        color_box = QtWidgets.QGroupBox("Colors")
        color_form = QtWidgets.QFormLayout(color_box)
        for channel, label in _COLOR_SPECS:
            button = QtWidgets.QPushButton()
            button.setObjectName(f"ParticleColorButton_{channel}")
            button.setFixedHeight(22)
            button.clicked.connect(lambda _checked=False, ch=channel: self._pick_color(ch))
            color_form.addRow(label, button)
            self._color_buttons[channel] = button
        form_layout.addWidget(color_box)

        for section, rows in _SCALAR_SPECS.items():
            box = QtWidgets.QGroupBox(section)
            grid = QtWidgets.QFormLayout(box)
            for channel, label, minimum, maximum, step, decimals in rows:
                spin = QtWidgets.QDoubleSpinBox()
                spin.setObjectName(f"ParticleSpin_{channel}")
                spin.setRange(minimum, maximum)
                spin.setSingleStep(step)
                spin.setDecimals(decimals)
                spin.valueChanged.connect(self._on_param_changed)
                grid.addRow(label, spin)
                self._scalar_widgets[channel] = spin
            form_layout.addWidget(box)

        flags_box = QtWidgets.QGroupBox("Flags")
        flags_grid = QtWidgets.QGridLayout(flags_box)
        for index, (flag, label) in enumerate(_FLAG_SPECS):
            check = QtWidgets.QCheckBox(label)
            check.toggled.connect(self._on_param_changed)
            flags_grid.addWidget(check, index // 2, index % 2)
            self._flag_checks[int(flag)] = check
        form_layout.addWidget(flags_box)

        self._build_forces_section(form_layout)
        form_layout.addStretch(1)

        self.statusBar().showMessage("Load a model to edit its emitters.", 8000)

    def _build_forces_section(self, form_layout: QtWidgets.QVBoxLayout) -> None:
        """Ghost Studio force-field + dynamic-colour controls.

        These are non-KOTOR authoring extensions (adapted from the GPU gravity
        wells in conanwu777/particle_system) that add swirling/orbiting motion
        and animated hue cycling on top of the stock emitter model.
        """
        box = QtWidgets.QGroupBox("Force Fields & Dynamic Colour (Ghost Studio)")
        layout = QtWidgets.QVBoxLayout(box)

        hue_form = QtWidgets.QFormLayout()
        self.hue_cycle_spin = QtWidgets.QDoubleSpinBox()
        self.hue_cycle_spin.setRange(0.0, 10.0)
        self.hue_cycle_spin.setSingleStep(0.05)
        self.hue_cycle_spin.setDecimals(3)
        self.hue_cycle_spin.setToolTip(
            "Rotate each particle's hue over its lifetime (turns/second). "
            "0 keeps the authored colours."
        )
        self.hue_cycle_spin.valueChanged.connect(self._on_param_changed)
        hue_form.addRow("Hue Cycle (turns/s)", self.hue_cycle_spin)
        layout.addLayout(hue_form)

        self.force_table = QtWidgets.QTableWidget(0, 6)
        self.force_table.setObjectName("ParticleForceTable")
        self.force_table.setHorizontalHeaderLabels(
            ["Mode", "X", "Y", "Z", "Strength", "Radius"]
        )
        self.force_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.Stretch
        )
        self.force_table.verticalHeader().setVisible(False)
        self.force_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.force_table.setMaximumHeight(160)
        self.force_table.itemChanged.connect(self._on_force_table_changed)
        layout.addWidget(self.force_table)

        buttons = QtWidgets.QHBoxLayout()
        for label, mode in (("+ Attractor", "attract"),
                            ("+ Repeller", "repel"),
                            ("+ Vortex", "vortex")):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _c=False, m=mode: self._add_force_field(m))
            buttons.addWidget(button)
        remove_button = QtWidgets.QPushButton("Remove")
        remove_button.clicked.connect(self._remove_selected_force_field)
        buttons.addWidget(remove_button)
        layout.addLayout(buttons)

        form_layout.addWidget(box)

    def _refresh_force_table(self) -> None:
        prev = self._updating_widgets
        self._updating_widgets = True
        try:
            self.force_table.setRowCount(0)
            defn = self._definition
            if defn is None:
                return
            for fld in defn.force_fields:
                row = self.force_table.rowCount()
                self.force_table.insertRow(row)
                mode_item = QtWidgets.QTableWidgetItem(str(fld.mode))
                mode_item.setFlags(mode_item.flags() & ~QtCore.Qt.ItemIsEditable)
                self.force_table.setItem(row, 0, mode_item)
                cells = (fld.position[0], fld.position[1], fld.position[2],
                         fld.strength, fld.radius)
                for col, value in enumerate(cells, start=1):
                    self.force_table.setItem(row, col, QtWidgets.QTableWidgetItem(f"{value:.3f}"))
        finally:
            self._updating_widgets = prev

    def _add_force_field(self, mode: str) -> None:
        if self._definition is None:
            self.statusBar().showMessage("Select an emitter before adding a force.", 6000)
            return
        self._definition.force_fields.append(
            ForceField(mode=mode, position=(0.0, 0.0, 1.0), strength=2.0, radius=0.0)
        )
        self._refresh_force_table()
        self._commit_definition()

    def _remove_selected_force_field(self) -> None:
        if self._definition is None:
            return
        rows = sorted({idx.row() for idx in self.force_table.selectedIndexes()}, reverse=True)
        if not rows:
            return
        for row in rows:
            if 0 <= row < len(self._definition.force_fields):
                del self._definition.force_fields[row]
        self._refresh_force_table()
        self._commit_definition()

    def _on_force_table_changed(self, _item) -> None:
        if self._updating_widgets or self._definition is None:
            return

        def _num(row: int, col: int, default: float = 0.0) -> float:
            item = self.force_table.item(row, col)
            try:
                return float(item.text()) if item is not None else default
            except (TypeError, ValueError):
                return default

        fields: List[ForceField] = []
        for row in range(self.force_table.rowCount()):
            mode_item = self.force_table.item(row, 0)
            mode = mode_item.text() if mode_item is not None else "attract"
            fields.append(ForceField(
                mode=mode,
                position=(_num(row, 1), _num(row, 2), _num(row, 3)),
                strength=_num(row, 4, 1.0),
                radius=max(0.0, _num(row, 5, 0.0)),
            ))
        self._definition.force_fields = fields
        self._commit_definition()

    # ── Theme/layout hooks ───────────────────────────────────────────────────
    def apply_ghost_theme(self, theme) -> None:
        hook = getattr(self.viewport, "apply_ghost_theme", None)
        if callable(hook):
            try:
                hook(theme)
            except Exception:
                pass

    def apply_ghost_layout(self, layout) -> None:  # stable layout ID surface
        return None

    # ── Model loading ────────────────────────────────────────────────────────
    def set_resource_manager(self, manager) -> None:
        self._resource_manager = manager

    def _manager(self):
        if self._resource_manager is not None:
            return self._resource_manager
        parent = self.parent()
        getter = getattr(parent, "_get_resource_manager", None)
        if callable(getter):
            try:
                self._resource_manager = getter()
            except Exception:
                self._resource_manager = None
        return self._resource_manager

    def _load_requested_model(self) -> None:
        resref = self.resref_edit.text().strip().lower()
        game = self.game_combo.currentText().strip().upper() or "K1"
        if not resref:
            return
        manager = self._manager()
        if manager is None:
            self.statusBar().showMessage("No game resource manager available.", 8000)
            return
        model = manager.load_model(resref, game)
        if model is None:
            self.statusBar().showMessage(f"Model not found: {game}:{resref}", 8000)
            return
        self.use_model(model, game, f"{game}:{resref}")

    def _use_main_window_model(self) -> None:
        parent = self.parent()
        model = getattr(parent, "_current_model", None)
        if model is None:
            self.statusBar().showMessage("The main window has no loaded model.", 8000)
            return
        game = str(getattr(parent, "_current_game", "K1") or "K1").upper()
        self.use_model(model, game, str(getattr(model, "name", "model")))

    def use_model(self, model, game: str, label: str) -> None:
        self._stop_animation()
        self._model = model
        self._model_game = "K2" if str(game).upper().startswith("K2") else "K1"
        self.game_combo.setCurrentText(self._model_game)
        manager = self._manager()
        set_manager = getattr(self.viewport, "set_resource_manager", None)
        if manager is not None and callable(set_manager):
            set_manager(manager, self._model_game)
        self.viewport.load_model(model, "")
        frame_all = getattr(self.viewport, "frame_all", None)
        if callable(frame_all):
            try:
                frame_all()
            except Exception:
                pass
        self._refresh_emitter_tree()
        self._populate_animations()
        self.statusBar().showMessage(
            f"Loaded {label} — {self.model_group.childCount()} emitter node(s).", 8000
        )

    # ── Emitter tree ─────────────────────────────────────────────────────────
    def _refresh_emitter_tree(self) -> None:
        self.model_group.takeChildren()
        if self._model is None:
            return
        for node in emitter_nodes(self._model):
            params = getattr(node, "emitter_params", {}) or {}
            info = f"{params.get('update', '')}/{params.get('blend', '')} {params.get('texture', '')}"
            item = QtWidgets.QTreeWidgetItem([str(getattr(node, "name", "emitter")), info])
            item.setData(0, QtCore.Qt.UserRole, ("node", id(node)))
            self.model_group.addChild(item)
        self.model_group.setText(1, f"{self.model_group.childCount()} emitters")
        self.model_group.setExpanded(True)

    def _node_by_id(self, node_id: int):
        if self._model is None:
            return None
        for node in emitter_nodes(self._model):
            if id(node) == node_id:
                return node
        return None

    def _template_by_key(self, game: str, key: str) -> Optional[EmitterTemplate]:
        for template in self._templates.get(game, []):
            if template.key == key:
                return template
        return None

    def _on_tree_selection(self) -> None:
        items = self.tree.selectedItems()
        if not items:
            return
        payload = items[0].data(0, QtCore.Qt.UserRole)
        if not payload:
            return
        kind, ref = payload
        if kind == "node":
            node = self._node_by_id(ref)
            if node is not None:
                self._bind_node(node)
        elif kind == "template":
            game, key = ref
            template = self._template_by_key(game, key)
            if template is not None:
                self.selected_label.setText(
                    f"Template {template.model}:{template.node} ({template.game}) — "
                    "double-click to apply to the selected emitter"
                )

    def _on_tree_double_clicked(self, item, _column: int) -> None:
        payload = item.data(0, QtCore.Qt.UserRole)
        if not payload:
            return
        kind, ref = payload
        if kind == "template":
            game, key = ref
            template = self._template_by_key(game, key)
            if template is not None:
                self._apply_template(template)

    def _on_tree_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if item is None:
            return
        payload = item.data(0, QtCore.Qt.UserRole)
        if not payload or payload[0] != "template":
            return
        game, key = payload[1]
        template = self._template_by_key(game, key)
        if template is None:
            return
        menu = QtWidgets.QMenu(self)
        apply_action = menu.addAction("Apply to Selected Emitter")
        add_action = menu.addAction("Add as New Emitter Node")
        load_action = menu.addAction("Load Source Model")
        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen is apply_action:
            self._apply_template(template)
        elif chosen is add_action:
            self._add_template_as_node(template)
        elif chosen is load_action:
            self.game_combo.setCurrentText(template.game)
            self.resref_edit.setText(template.model)
            self._load_requested_model()

    # ── Parameter binding ────────────────────────────────────────────────────
    def _bind_node(self, node) -> None:
        self._selected_node = node
        self._definition = EmitterDefinition.from_node(node)
        self._updating_widgets = True
        try:
            defn = self._definition
            keyed = [name for name, rows in defn.channels.items() if len(rows) > 1]
            suffix = f"  (keyed channels: {', '.join(sorted(keyed))})" if keyed else ""
            self.selected_label.setText(f"Emitter: {defn.name}{suffix}")
            self.update_combo.setCurrentText(defn.update or "Fountain")
            self.render_combo.setCurrentText(defn.render or "Normal")
            self.blend_combo.setCurrentText(defn.blend or "Normal")
            self.texture_edit.setText(defn.texture)
            self.grid_x_spin.setValue(int(defn.grid_x))
            self.grid_y_spin.setValue(int(defn.grid_y))
            self.loop_check.setChecked(bool(defn.loop))
            self.twosided_check.setChecked(bool(defn.two_sided_texture))
            self.frame_blend_check.setChecked(bool(defn.frame_blending))
            self.render_order_spin.setValue(int(defn.render_order))
            for channel, spin in self._scalar_widgets.items():
                spin.setValue(float(defn.value(channel)))
            for channel, button in self._color_buttons.items():
                self._set_color_button(button, defn.color(channel))
            flags = int(defn.flags)
            for bit, check in self._flag_checks.items():
                check.setChecked(bool(flags & bit))
            self.hue_cycle_spin.setValue(float(getattr(defn, "hue_cycle_speed", 0.0) or 0.0))
            self._refresh_force_table()
        finally:
            self._updating_widgets = False

    @staticmethod
    def _set_color_button(button: QtWidgets.QPushButton, rgb) -> None:
        color = QtGui.QColor.fromRgbF(
            max(0.0, min(1.0, rgb[0])),
            max(0.0, min(1.0, rgb[1])),
            max(0.0, min(1.0, rgb[2])),
        )
        button.setText(f"{rgb[0]:.2f}, {rgb[1]:.2f}, {rgb[2]:.2f}")
        button.setStyleSheet(
            f"background-color: {color.name()};"
            f" color: {'black' if color.lightnessF() > 0.5 else 'white'};"
        )
        button.setProperty("_rgb", tuple(float(v) for v in rgb))

    def _pick_color(self, channel: str) -> None:
        if self._definition is None:
            return
        current = self._definition.color(channel)
        initial = QtGui.QColor.fromRgbF(
            max(0.0, min(1.0, current[0])),
            max(0.0, min(1.0, current[1])),
            max(0.0, min(1.0, current[2])),
        )
        picked = QtWidgets.QColorDialog.getColor(initial, self, f"Pick {channel}")
        if not picked.isValid():
            return
        self._definition.set_color(channel, (picked.redF(), picked.greenF(), picked.blueF()))
        self._set_color_button(self._color_buttons[channel], self._definition.color(channel))
        self._commit_definition()

    def _on_param_changed(self, *_args) -> None:
        if self._updating_widgets or self._definition is None:
            return
        defn = self._definition
        defn.update = self.update_combo.currentText()
        defn.render = self.render_combo.currentText()
        defn.blend = self.blend_combo.currentText()
        defn.texture = self.texture_edit.text().strip()
        defn.grid_x = int(self.grid_x_spin.value())
        defn.grid_y = int(self.grid_y_spin.value())
        defn.loop = 1 if self.loop_check.isChecked() else 0
        defn.two_sided_texture = 1 if self.twosided_check.isChecked() else 0
        defn.frame_blending = 1 if self.frame_blend_check.isChecked() else 0
        defn.render_order = int(self.render_order_spin.value())
        for channel, spin in self._scalar_widgets.items():
            value = float(spin.value())
            if channel in defn.channels or abs(value - defn.value(channel)) > 1e-9:
                defn.set_value(channel, value)
        flags = 0
        for bit, check in self._flag_checks.items():
            if check.isChecked():
                flags |= bit
        defn.flags = flags
        defn.hue_cycle_speed = float(self.hue_cycle_spin.value())
        self._commit_definition()

    def _commit_definition(self) -> None:
        node = self._selected_node
        if node is None or self._definition is None:
            return
        self._definition.apply_to_node(node)
        self._restart_node_particles(node)

    def _restart_node_particles(self, node) -> None:
        renderer = getattr(self.viewport, "_gpu_renderer", None)
        invalidate = getattr(renderer, "invalidate_particles", None)
        if callable(invalidate):
            try:
                invalidate(node)
            except Exception:
                pass
        request = getattr(self.viewport, "_request_render", None)
        if callable(request):
            request(fast=True, reason="emitter parameters changed", scene=True)

    # ── Animation preview ────────────────────────────────────────────────────
    def _populate_animations(self) -> None:
        self.anim_combo.clear()
        for anim in getattr(self._model, "animations", None) or []:
            self.anim_combo.addItem(str(getattr(anim, "name", "") or ""))
        on_index = self.anim_combo.findText("on")
        if on_index >= 0:
            self.anim_combo.setCurrentIndex(on_index)

    def _play_animation(self) -> None:
        if self._model is None:
            return
        name = self.anim_combo.currentText().strip()
        if not name:
            return
        from src.core.animation.animation_engine import AnimationEngine

        self._anim_engine = AnimationEngine(self._model)
        if not self._anim_engine.play(name, loop=True):
            self._anim_engine = None
            return
        anim = self._anim_engine.current_animation
        self._anim_length = float(getattr(anim, "length", 0.0) or 0.0)
        self._anim_wall = time_module.perf_counter()
        set_active = getattr(self.viewport, "set_animation_playback_active", None)
        if callable(set_active):
            set_active(True, "particle editor animation")
        self._anim_timer.start()

    def _stop_animation(self) -> None:
        self._anim_timer.stop()
        self._anim_engine = None
        clear = getattr(self.viewport, "clear_animation_pose", None)
        if callable(clear):
            try:
                clear()
            except Exception:
                pass

    def _on_anim_tick(self) -> None:
        engine = self._anim_engine
        if engine is None or self._model is None:
            self._anim_timer.stop()
            return
        now = time_module.perf_counter()
        delta = min(0.25, max(0.0, now - self._anim_wall))
        self._anim_wall = now
        advance = getattr(engine, "advance", None)
        if callable(advance):
            advance(delta)
        else:
            engine._time = (engine._time + delta) % max(0.001, self._anim_length or 0.001)
        pose = engine.evaluate()
        anim = engine.current_animation
        self.viewport.set_animation_pose(
            pose,
            name=str(getattr(anim, "name", "") or ""),
            time=float(engine.current_time),
            length=self._anim_length,
        )

    # ── Template library ─────────────────────────────────────────────────────
    def _begin_gc_guard(self) -> None:
        self._gc_guard_count += 1
        if self._gc_guard_count == 1:
            self._gc_guard_was_enabled = gc.isenabled()
            gc.disable()
            self._gc_guard_timer.start()

    def _end_gc_guard(self) -> None:
        self._gc_guard_count = max(0, self._gc_guard_count - 1)
        if self._gc_guard_count == 0:
            self._gc_guard_timer.stop()
            if self._gc_guard_was_enabled:
                gc.enable()
            gc.collect()

    def _library_root(self) -> Path:
        """Directory whose ``Saved/ParticleLibrary`` holds the scan caches.

        Defaults to the app root (packaged builds).  Source checkouts run with
        an app root inside the package tree, so when no cache exists there but
        the repository root has one, use the repository root instead.
        """
        root = self._app_root
        if any(library_cache_path(root, game).is_file() for game in _GAMES):
            return root
        for candidate in [root, *root.parents]:
            if (candidate / "GhostRigger.sln").exists():
                if any(library_cache_path(candidate, game).is_file() for game in _GAMES):
                    return candidate
                break
        return root

    def _load_cached_libraries(self) -> None:
        """Load scan caches off the UI thread; retail libraries hold ~12k emitters."""

        def worker() -> None:
            try:
                for game in _GAMES:
                    templates = load_library(library_cache_path(self._library_root(), game))
                    if templates:
                        self._templates[game] = templates
                    self.scanFinished.emit(game, len(templates))
            finally:
                self.workerDone.emit()

        self._begin_gc_guard()
        threading.Thread(target=worker, daemon=True, name="particle-library-load").start()

    def _populate_template_group(self, game: str, group: QtWidgets.QTreeWidgetItem) -> None:
        self.tree.setUpdatesEnabled(False)
        try:
            group.takeChildren()
            templates = self._templates.get(game, [])
            by_model: Dict[str, List[EmitterTemplate]] = {}
            for template in templates:
                by_model.setdefault(template.model, []).append(template)
            model_items: List[QtWidgets.QTreeWidgetItem] = []
            for model_name in sorted(by_model):
                model_item = QtWidgets.QTreeWidgetItem([model_name, f"{len(by_model[model_name])}"])
                children: List[QtWidgets.QTreeWidgetItem] = []
                for template in by_model[model_name]:
                    defn = template.definition
                    info = f"{defn.get('update', '')}/{defn.get('blend', '')} {defn.get('texture', '')}"
                    child = QtWidgets.QTreeWidgetItem([template.node, info])
                    child.setData(0, QtCore.Qt.UserRole, ("template", (game, template.key)))
                    children.append(child)
                model_item.addChildren(children)
                model_items.append(model_item)
            group.addChildren(model_items)
            group.setText(1, f"{len(templates)} emitters" if templates else "not scanned")
        finally:
            self.tree.setUpdatesEnabled(True)

    def _start_library_scan(self) -> None:
        if self._scan_thread is not None and self._scan_thread.is_alive():
            self._scan_cancel.set()
            self.status_label.setText(" cancelling scan...")
            return
        manager = self._manager()
        if manager is None:
            self.statusBar().showMessage("No game resource manager available for scanning.", 8000)
            return
        self._scan_cancel.clear()
        self.scan_action.setText("Cancel Scan")

        def worker() -> None:
            try:
                for game in _GAMES:
                    if self._scan_cancel.is_set():
                        break
                    templates = scan_resource_manager_library(
                        manager,
                        game,
                        progress=lambda resref, index, total, g=game: self.scanProgress.emit(
                            f"{g}: {resref}", index, total
                        ),
                        cancel=self._scan_cancel.is_set,
                    )
                    if templates and not self._scan_cancel.is_set():
                        save_library(library_cache_path(self._library_root(), game), game, templates)
                        self._templates[game] = templates
                    self.scanFinished.emit(game, len(templates))
            finally:
                self.scanProgress.emit("", 0, 0)
                self.workerDone.emit()

        self._begin_gc_guard()
        self._scan_thread = threading.Thread(
            target=worker, daemon=True, name="particle-library-scan"
        )
        self._scan_thread.start()

    def _on_scan_progress(self, label: str, index: int, total: int) -> None:
        if not label and total == 0:
            self.scan_action.setText("Scan Game Libraries")
            self.status_label.setText("")
            return
        self.status_label.setText(f"  scanning {label} ({index}/{total})")

    def _on_scan_finished(self, game: str, count: int) -> None:
        group = self.k1_group if game == "K1" else self.k2_group
        self._populate_template_group(game, group)
        if count:
            self.statusBar().showMessage(f"{game} emitter library: {count} templates.", 8000)

    # ── Template application ─────────────────────────────────────────────────
    def _apply_template(self, template: EmitterTemplate) -> None:
        node = self._selected_node
        if node is None:
            self.statusBar().showMessage("Select a model emitter first, then apply the template.", 8000)
            return
        defn = template.emitter_definition()
        defn.name = str(getattr(node, "name", defn.name))
        defn.apply_to_node(node)
        self._bind_node(node)
        self._restart_node_particles(node)
        self._refresh_emitter_tree()
        self.statusBar().showMessage(
            f"Applied {template.model}:{template.node} to {defn.name}.", 8000
        )

    def _add_template_as_node(self, template: EmitterTemplate) -> None:
        if self._model is None or getattr(self._model, "root_node", None) is None:
            self.statusBar().showMessage("Load a model before adding emitter nodes.", 8000)
            return
        from src.core.geometry.model_data import ModelNode, NodeFlags

        existing = {str(getattr(node, "name", "")).lower() for node in self._model.all_nodes()}
        base_name = f"{template.node}_new"
        name = base_name
        suffix = 1
        while name.lower() in existing:
            suffix += 1
            name = f"{base_name}{suffix}"

        node = ModelNode(
            name=name,
            flags=int(NodeFlags.HEADER) | int(NodeFlags.EMITTER),
        )
        node.position = (0.0, 0.0, 1.0)
        node.rotation = (0.0, 0.0, 0.0, 1.0)
        defn = template.emitter_definition()
        defn.name = name
        defn.apply_to_node(node)
        root = self._model.root_node
        node.parent = root
        root.children.append(node)

        renderer = getattr(self.viewport, "_gpu_renderer", None)
        invalidate_all = getattr(renderer, "invalidate_particles", None)
        if callable(invalidate_all):
            try:
                invalidate_all(None)
            except Exception:
                pass
        invalidate_cache = getattr(renderer, "invalidate_node_cache", None)
        if callable(invalidate_cache):
            try:
                invalidate_cache()
            except Exception:
                pass
        self._refresh_emitter_tree()
        request = getattr(self.viewport, "_request_render", None)
        if callable(request):
            request(fast=True, reason="emitter node added", scene=True, resources=True)
        self.statusBar().showMessage(f"Added emitter node {name} from template.", 8000)

    # ── Lifecycle ────────────────────────────────────────────────────────────
    def closeEvent(self, event) -> None:
        self._scan_cancel.set()
        self._stop_animation()
        # Never leave automatic GC disabled past this window's lifetime.
        self._gc_guard_timer.stop()
        if self._gc_guard_count > 0 and self._gc_guard_was_enabled:
            gc.enable()
        self._gc_guard_count = 0
        super().closeEvent(event)
