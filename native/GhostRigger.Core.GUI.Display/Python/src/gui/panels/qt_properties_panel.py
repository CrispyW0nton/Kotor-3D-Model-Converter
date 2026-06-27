"""Qt properties panel for the GhostRigger migration."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.gui.qt_lib.assets.qt_theme import C, heading
from src.measurement.dimension_calculator import DimensionCalculator
from src.measurement.measurement_formatter import MeasurementFormatter
from src.measurement.unit_settings import MeasurementSettings
from src.measurement.unit_system import UNIT_SYMBOLS, UnitSystem

# Quaternion <-> Euler conversion lives in the shared math package so the
# convention matches the viewport and camera panels exactly.  (Transform
# skill: "Shared math belongs in src/math".)
from src.math.camera_math import euler_degrees_to_quat, quat_to_euler_degrees

# ── CharacterMode wiring (M1 / T105) ────────────────────────────────────────
# Imported lazily-safe: ``model_data`` is a pure-Python module but the
# enclosing ``src.core`` package imports the pykotor loader stack at
# import time.  We isolate the failure so the Qt panel still loads in
# environments where pykotor is missing (the badge simply stays empty).
try:
    from src.core.geometry.model_data import CharacterMode, detect_character_mode
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
    "mode_module":        "#2E86DE",   # blue
    "mode_supermodel":    "#9B59B6",   # purple
    "mode_creature":      "#27AE60",   # green
    "mode_ambiguous":     "#7F8C8D",   # grey
    "mode_unsupported":   "#C0392B",   # red
}

# Maps each badge ``icon_key`` to a semantic theme token.  Themes may
# override the badge swatch colour by defining ``characterMode.*`` keys;
# when a token is unset the hex default above is used instead.  (Issue #11
# theme-token migration: badges no longer bypass the token system.)
_CHARACTER_MODE_BADGE_TOKENS = {
    "mode_headless_body": "characterMode.headlessBody",
    "mode_head":          "characterMode.head",
    "mode_humanoid":      "characterMode.humanoid",
    "mode_module":        "characterMode.module",
    "mode_supermodel":    "characterMode.supermodel",
    "mode_creature":      "characterMode.creature",
    "mode_ambiguous":     "characterMode.ambiguous",
    "mode_unsupported":   "characterMode.unsupported",
}


class QtPropertiesPanel(QtWidgets.QWidget):
    positionApplied = QtCore.Signal(object, float, float, float)
    rotationApplied = QtCore.Signal(object, float, float, float)
    scaleApplied = QtCore.Signal(object, float, float, float)
    moduleMeshSelected = QtCore.Signal(object)
    moduleMeshesSelected = QtCore.Signal(list)
    moduleMeshVisibilityChanged = QtCore.Signal()
    moduleMeshesWindowRequested = QtCore.Signal()
    # Emitted whenever the user manually overrides the CharacterMode via
    # the override QComboBox.  Payload: the new :class:`CharacterMode`
    # value (or ``None`` when the enum isn't importable).  The Character
    # Builder toolbar / scene controller should connect to this and call
    # ``scene.set_mode(mode, locked=True)`` to honour the choice.
    characterModeChanged = QtCore.Signal(object)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, *, module_browser_enabled: bool = True):
        QtWidgets.QWidget.__init__(self, parent)
        self._current_model = None
        self._mesh_items: dict[QtWidgets.QTreeWidgetItem, object] = {}
        self._wall_items: dict[QtWidgets.QTreeWidgetItem, object] = {}
        self._walkmesh_items: dict[QtWidgets.QTreeWidgetItem, object] = {}
        self._null_mesh_items: dict[QtWidgets.QTreeWidgetItem, object] = {}
        self._suppress_mesh_signal = False
        self._module_browser_enabled = bool(module_browser_enabled)
        self._current_node = None
        self.unit_system = UnitSystem()
        self.measurement_settings = MeasurementSettings()
        self.dimension_calculator = DimensionCalculator()
        self._suppress_mode_signal = False
        self._suppress_scale_signal = False
        # Active theme token resolver; ``None`` until the first theme apply.
        # Colour helpers below fall back to the shared legacy palette ``C``
        # (kept in sync by ``update_legacy_palette``) when no theme is set.
        self._theme = None
        self._character_mode_icon_key = "mode_ambiguous"
        self._build()

    # ── Theme-token accessors (issue #11) ────────────────────────────
    def _color(self, token: str, legacy_key: str) -> str:
        """Resolve a colour through the active theme token system.

        Falls back to the shared compatibility palette ``C`` (kept in sync
        with the active theme by :func:`update_legacy_palette`) when no
        theme has been applied yet, preserving the pre-theme appearance.
        """
        if self._theme is not None:
            resolved = self._theme.color(token)
            if resolved:
                return resolved
        return C.get(legacy_key, "")

    def _badge_color(self, icon_key: str) -> str:
        """Colour for a CharacterMode badge swatch.

        Uses the ``characterMode.<iconKey>`` token when a theme is loaded
        (allowing themes to override the categorical mode colours),
        otherwise the hex default from :data:`_CHARACTER_MODE_BADGE_COLORS`.
        """
        default = _CHARACTER_MODE_BADGE_COLORS.get(
            icon_key, _CHARACTER_MODE_BADGE_COLORS["mode_ambiguous"]
        )
        token = _CHARACTER_MODE_BADGE_TOKENS.get(icon_key)
        if token and self._theme is not None:
            resolved = self._theme.color(token)
            if resolved:
                return resolved
        return default

    def _apply_badge_stylesheet(self) -> None:
        if getattr(self, "character_mode_badge", None) is None:
            return
        color = self._badge_color(self._character_mode_icon_key)
        self.character_mode_badge.setStyleSheet(
            "QLabel { "
            f"background:{color}; "
            "color:#FFFFFF; "
            "padding:2px 8px; "
            "border-radius:6px; "
            "font-weight:bold; "
            "}"
        )

    def apply_ghost_theme(self, theme) -> None:
        """Re-resolve panel colours through the active theme tokens."""
        self._theme = theme
        gold = self._color("text.gold", "gold")
        if getattr(self, "transform_group", None) is not None:
            self.transform_group.setStyleSheet(f"QGroupBox {{ color:{gold}; }}")
        if getattr(self, "character_mode_group", None) is not None:
            self.character_mode_group.setStyleSheet(f"QGroupBox {{ color:{gold}; }}")
        text2 = self._color("text.secondary", "text2")
        for attr in (
            "module_mesh_count", "module_wall_mesh_count",
            "module_null_mesh_count", "module_walkmesh_count",
        ):
            label = getattr(self, attr, None)
            if label is not None:
                label.setStyleSheet(f"color:{text2};")
        self._apply_badge_stylesheet()
        # Re-tint mesh-tree rows so an already-populated tree follows the
        # new theme without requiring a manual reload.
        if hasattr(self, "_refresh_module_mesh_rows"):
            try:
                self._refresh_module_mesh_rows()
            except Exception:
                pass

    def apply_native_theme(self) -> None:
        """Native-mode hook (no token palette); colours fall back to ``C``."""
        self._theme = None

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)
        self.properties_heading = heading("Properties")
        root.addWidget(self.properties_heading)

        # ── CharacterMode badge + override (M1 / T105) ────────────────────
        self._build_character_mode_row(root)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setMinimumWidth(0)
        self.tabs.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.text = QtWidgets.QTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QtWidgets.QTextEdit.WidgetWidth)
        self.text.setMinimumWidth(0)
        self.text.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.text.setPlainText("No model loaded.")
        self.tabs.addTab(self.text, "General")
        self.module_tab = None
        if self._module_browser_enabled:
            self.module_tab = self._build_module_mesh_tab()
            self.tabs.addTab(self.module_tab, "Module Meshes")
        root.addWidget(self.tabs, 1)

        self.transform_group = QtWidgets.QGroupBox("Node Transform (editable)")
        self.transform_group.setStyleSheet(f"QGroupBox {{ color:{self._color('text.gold', 'gold')}; }}")
        tform = QtWidgets.QVBoxLayout(self.transform_group)
        tform.setContentsMargins(6, 6, 6, 6)
        tform.setSpacing(4)

        # ── Position (scene units) ────────────────────────────────────
        # x/y/z_spin keep their original names; the measurement-settings
        # path below keys off them for precision/suffix updates.
        self.x_spin = self._spin()
        self.y_spin = self._spin()
        self.z_spin = self._spin()
        tform.addLayout(self._transform_row("Pos", (self.x_spin, self.y_spin, self.z_spin)))

        # ── Rotation (Euler degrees, X/Y/Z) ───────────────────────────
        self.rx_spin = self._rotation_spin()
        self.ry_spin = self._rotation_spin()
        self.rz_spin = self._rotation_spin()
        tform.addLayout(self._transform_row("Rot", (self.rx_spin, self.ry_spin, self.rz_spin)))

        # ── Scale (per-axis multiplier) ───────────────────────────────
        self.sx_spin = self._scale_spin()
        self.sy_spin = self._scale_spin()
        self.sz_spin = self._scale_spin()
        for spin in (self.sx_spin, self.sy_spin, self.sz_spin):
            spin.valueChanged.connect(self._on_scale_spin_changed)
        tform.addLayout(self._transform_row("Scl", (self.sx_spin, self.sy_spin, self.sz_spin)))

        # ── Uniform-scale link ────────────────────────────────────────
        self.uniform_scale_check = QtWidgets.QCheckBox("Uniform Scale")
        self.uniform_scale_check.setChecked(False)
        self.uniform_scale_check.setToolTip(
            "When checked, editing one axis updates all three scale values."
        )
        tform.addWidget(self.uniform_scale_check)

        apply_button = QtWidgets.QPushButton("Apply Transform")
        apply_button.clicked.connect(self._apply_transform)
        tform.addWidget(apply_button)
        root.addWidget(self.transform_group)
        # Visible by default; show_node()/show_model() manage its state.

    def set_measurement_settings(self, values: dict | MeasurementSettings | None) -> None:
        settings = values if isinstance(values, MeasurementSettings) else MeasurementSettings.from_dict(values)
        self.measurement_settings = settings
        self.unit_system.set_system_unit(settings.system_unit)
        self.unit_system.set_display_unit(settings.display_unit)
        symbol = UNIT_SYMBOLS.get(self.unit_system.display_unit, self.unit_system.display_unit)
        suffix = f" {symbol}"
        for spin in (self.x_spin, self.y_spin, self.z_spin):
            spin.setDecimals(settings.distance_precision)
            spin.setSuffix(suffix)
        if self._current_node is not None:
            self.show_node(self._current_node)
        elif self._current_model is not None:
            self.show_model(self._current_model)

    def set_module_browser_only(self, enabled: bool = True) -> None:
        if not self._module_browser_enabled or self.module_tab is None:
            return
        self.properties_heading.setText("Module Geometry")
        self.properties_heading.setVisible(not enabled)
        if hasattr(self, "character_mode_group"):
            self.character_mode_group.setVisible(not enabled)
        self.transform_group.setVisible(False)
        general_index = self.tabs.indexOf(self.text)
        if enabled and general_index >= 0:
            self.tabs.removeTab(general_index)
        elif not enabled and general_index < 0:
            self.tabs.insertTab(0, self.text, "General")
        self.tabs.setCurrentWidget(self.module_tab)

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
        self.module_mesh_count.setStyleSheet(f"color:{self._color('text.secondary', 'text2')};")
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
        self.module_mesh_tree.itemClicked.connect(self._on_module_mesh_item_clicked)
        self.module_mesh_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.module_mesh_tree.customContextMenuRequested.connect(self._show_module_browser_context_menu)
        self.module_mesh_tree.setRootIsDecorated(False)
        self.module_mesh_tree.setAlternatingRowColors(True)
        mesh_layout.addWidget(self.module_mesh_tree, 1)
        select_all_shortcut = QtGui.QShortcut(QtGui.QKeySequence.SelectAll, self.module_mesh_tree)
        select_all_shortcut.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
        select_all_shortcut.activated.connect(self.select_all_module_meshes)

        wall_page = QtWidgets.QWidget()
        wall_layout = QtWidgets.QVBoxLayout(wall_page)
        wall_layout.setContentsMargins(2, 2, 2, 2)
        wall_layout.setSpacing(4)
        self.module_wall_mesh_count = QtWidgets.QLabel("No walls.")
        self.module_wall_mesh_count.setStyleSheet(f"color:{self._color('text.secondary', 'text2')};")
        wall_layout.addWidget(self.module_wall_mesh_count)

        self.module_wall_mesh_filter = QtWidgets.QLineEdit()
        self.module_wall_mesh_filter.setPlaceholderText("Filter walls")
        self.module_wall_mesh_filter.textChanged.connect(self._filter_module_meshes)
        wall_layout.addWidget(self.module_wall_mesh_filter)

        self.module_wall_mesh_tree = QtWidgets.QTreeWidget()
        self.module_wall_mesh_tree.setColumnCount(6)
        self.module_wall_mesh_tree.setHeaderLabels(["Wall", "Verts", "Faces", "Texture", "Visible", "Group"])
        self.module_wall_mesh_tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.module_wall_mesh_tree.itemSelectionChanged.connect(self._on_module_mesh_selection_changed)
        self.module_wall_mesh_tree.itemClicked.connect(self._on_module_mesh_item_clicked)
        self.module_wall_mesh_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.module_wall_mesh_tree.customContextMenuRequested.connect(self._show_module_browser_context_menu)
        self.module_wall_mesh_tree.setRootIsDecorated(False)
        self.module_wall_mesh_tree.setAlternatingRowColors(True)
        wall_layout.addWidget(self.module_wall_mesh_tree, 1)
        select_all_wall_shortcut = QtGui.QShortcut(QtGui.QKeySequence.SelectAll, self.module_wall_mesh_tree)
        select_all_wall_shortcut.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
        select_all_wall_shortcut.activated.connect(self.select_all_module_meshes)

        null_page = QtWidgets.QWidget()
        null_layout = QtWidgets.QVBoxLayout(null_page)
        null_layout.setContentsMargins(2, 2, 2, 2)
        null_layout.setSpacing(4)
        self.module_null_mesh_count = QtWidgets.QLabel("No NULL meshes.")
        self.module_null_mesh_count.setStyleSheet(f"color:{self._color('text.secondary', 'text2')};")
        null_layout.addWidget(self.module_null_mesh_count)

        self.module_null_mesh_filter = QtWidgets.QLineEdit()
        self.module_null_mesh_filter.setPlaceholderText("Filter NULL meshes")
        self.module_null_mesh_filter.textChanged.connect(self._filter_module_meshes)
        null_layout.addWidget(self.module_null_mesh_filter)

        self.module_null_mesh_tree = QtWidgets.QTreeWidget()
        self.module_null_mesh_tree.setColumnCount(6)
        self.module_null_mesh_tree.setHeaderLabels(["NULL Mesh", "Verts", "Faces", "Texture", "Visible", "Group"])
        self.module_null_mesh_tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.module_null_mesh_tree.itemSelectionChanged.connect(self._on_module_mesh_selection_changed)
        self.module_null_mesh_tree.itemClicked.connect(self._on_module_mesh_item_clicked)
        self.module_null_mesh_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.module_null_mesh_tree.customContextMenuRequested.connect(self._show_module_browser_context_menu)
        self.module_null_mesh_tree.setRootIsDecorated(False)
        self.module_null_mesh_tree.setAlternatingRowColors(True)
        null_layout.addWidget(self.module_null_mesh_tree, 1)
        select_all_null_shortcut = QtGui.QShortcut(QtGui.QKeySequence.SelectAll, self.module_null_mesh_tree)
        select_all_null_shortcut.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
        select_all_null_shortcut.activated.connect(self.select_all_module_meshes)

        walk_page = QtWidgets.QWidget()
        walk_layout = QtWidgets.QVBoxLayout(walk_page)
        walk_layout.setContentsMargins(2, 2, 2, 2)
        walk_layout.setSpacing(4)
        self.module_walkmesh_count = QtWidgets.QLabel("No walkmeshes.")
        self.module_walkmesh_count.setStyleSheet(f"color:{self._color('text.secondary', 'text2')};")
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
        self.module_walkmesh_tree.itemClicked.connect(self._on_module_mesh_item_clicked)
        self.module_walkmesh_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.module_walkmesh_tree.customContextMenuRequested.connect(self._show_module_browser_context_menu)
        self.module_walkmesh_tree.setRootIsDecorated(False)
        self.module_walkmesh_tree.setAlternatingRowColors(True)
        walk_layout.addWidget(self.module_walkmesh_tree, 1)
        select_all_walk_shortcut = QtGui.QShortcut(QtGui.QKeySequence.SelectAll, self.module_walkmesh_tree)
        select_all_walk_shortcut.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
        select_all_walk_shortcut.activated.connect(self.select_all_module_meshes)

        self.module_browser_tabs.addTab(mesh_page, "Meshes")
        self.module_browser_tabs.addTab(wall_page, "Walls")
        self.module_browser_tabs.addTab(null_page, "NULL Meshes")
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

    def _show_module_browser_context_menu(self, pos: QtCore.QPoint) -> None:
        tree = self.sender()
        if not isinstance(tree, QtWidgets.QTreeWidget):
            return
        menu = QtWidgets.QMenu(tree)
        hide_action = menu.addAction("Hide Selected")
        unhide_action = menu.addAction("Unhide Selected")
        hide_unselected_action = menu.addAction("Hide Unselected")
        unhide_all_action = menu.addAction("Unhide All")
        has_selection = bool(self._selected_module_meshes())
        hide_action.setEnabled(has_selection)
        unhide_action.setEnabled(has_selection)
        has_any_module_mesh = bool(self._mesh_items or self._wall_items or self._null_mesh_items or self._walkmesh_items)
        hide_unselected_action.setEnabled(has_any_module_mesh)
        unhide_all_action.setEnabled(has_any_module_mesh)
        chosen = menu.exec(tree.viewport().mapToGlobal(pos))
        if chosen is hide_action:
            self._set_selected_meshes_hidden(True)
        elif chosen is unhide_action:
            self._set_selected_meshes_hidden(False)
        elif chosen is hide_unselected_action:
            self._hide_unselected_module_meshes()
        elif chosen is unhide_all_action:
            self._unhide_all_module_meshes()

    def _spin(self) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(-100000.0, 100000.0)
        spin.setDecimals(5)
        spin.setSingleStep(0.05)
        return spin

    def _rotation_spin(self) -> QtWidgets.QDoubleSpinBox:
        """Euler rotation spin box, degrees, -360..360, 2dp."""
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(-360.0, 360.0)
        spin.setDecimals(2)
        spin.setSingleStep(1.0)
        spin.setValue(0.0)
        spin.setSuffix("°")
        return spin

    def _scale_spin(self) -> QtWidgets.QDoubleSpinBox:
        """Per-axis scale spin box, 0.01..100.0, 3dp, default 1.0."""
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(0.01, 100.0)
        spin.setDecimals(3)
        spin.setSingleStep(0.1)
        spin.setValue(1.0)
        return spin

    def _transform_row(
        self, label: str, spins
    ) -> QtWidgets.QHBoxLayout:
        """A labelled X/Y/Z row of spin boxes for the transform group."""
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(4)
        row.addWidget(QtWidgets.QLabel(f"{label}:"))
        for axis, spin in zip(("X", "Y", "Z"), spins):
            row.addWidget(QtWidgets.QLabel(f"{axis}:"))
            row.addWidget(spin, 1)
        return row

    def _on_scale_spin_changed(self, value: float) -> None:
        """Propagate one scale axis to the other two when Uniform Scale is on."""
        if self._suppress_scale_signal or not self.uniform_scale_check.isChecked():
            return
        sender = self.sender()
        for spin in (self.sx_spin, self.sy_spin, self.sz_spin):
            if spin is not sender:
                spin.blockSignals(True)
                spin.setValue(value)
                spin.blockSignals(False)

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
        self.character_mode_group = QtWidgets.QGroupBox("Character Mode")
        self.character_mode_group.setStyleSheet(f"QGroupBox {{ color:{self._color('text.gold', 'gold')}; }}")
        self.character_mode_group.setMinimumWidth(0)
        self.character_mode_group.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        grid = QtWidgets.QGridLayout(self.character_mode_group)
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setHorizontalSpacing(6)

        # ── Read-only badge ─────────────────────────────────────────────
        self.character_mode_badge = QtWidgets.QLabel("(unknown)")
        self.character_mode_badge.setAlignment(QtCore.Qt.AlignCenter)
        self.character_mode_badge.setMinimumWidth(0)
        self.character_mode_badge.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        self._character_mode_icon_key = "mode_ambiguous"
        self._apply_badge_stylesheet()
        grid.addWidget(QtWidgets.QLabel("Detected:"), 0, 0)
        grid.addWidget(self.character_mode_badge, 0, 1)

        # ── Manual-override combo ───────────────────────────────────────
        self.character_mode_combo = QtWidgets.QComboBox()
        self.character_mode_combo.setMinimumWidth(0)
        self.character_mode_combo.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
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
        grid.setColumnStretch(1, 1)

        parent_layout.addWidget(self.character_mode_group)

    def _update_character_mode_badge(self, mode) -> None:
        """Refresh the badge label + colour to reflect *mode*.

        Accepts a :class:`CharacterMode`, ``None`` (clears the badge),
        or any value with a ``.display_name`` / ``.icon_key`` interface
        for forward compatibility.
        """
        if mode is None:
            self.character_mode_badge.setText("(unknown)")
            self._character_mode_icon_key = "mode_ambiguous"
        else:
            display = getattr(mode, "display_name", str(mode))
            self._character_mode_icon_key = getattr(mode, "icon_key", "mode_ambiguous")
            self.character_mode_badge.setText(display.upper())
        self._apply_badge_stylesheet()

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
        x = self.unit_system.to_system_units(self.x_spin.value())
        y = self.unit_system.to_system_units(self.y_spin.value())
        z = self.unit_system.to_system_units(self.z_spin.value())
        # Rotation is edited as Euler degrees (X/Y/Z) but stored on the node
        # as a quaternion (x, y, z, w).  Use the shared camera_math helper so
        # the convention matches the viewport and camera panels.
        rx = float(self.rx_spin.value())
        ry = float(self.ry_spin.value())
        rz = float(self.rz_spin.value())
        sx = float(self.sx_spin.value())
        sy = float(self.sy_spin.value())
        sz = float(self.sz_spin.value())
        try:
            before = (
                tuple(getattr(node, "position", (0.0, 0.0, 0.0))),
                tuple(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))),
            )
            setattr(node, "_gr_undo_before_transform", before)
            node.position = (x, y, z)
            node.rotation = euler_degrees_to_quat((rx, ry, rz))
            # Scale lives on ``_gr_scale`` when present (the dimension
            # calculator's preferred attribute), otherwise on ``scale`` so the
            # write lands where the read looks.
            scale_attr = "_gr_scale" if hasattr(node, "_gr_scale") else "scale"
            setattr(node, scale_attr, (sx, sy, sz))
        finally:
            self.positionApplied.emit(node, x, y, z)
            self.rotationApplied.emit(node, rx, ry, rz)
            self.scaleApplied.emit(node, sx, sy, sz)

    def show_model(self, model) -> None:
        if not model:
            self._current_model = None
            self._current_node = None
            self.text.setPlainText("No model loaded.")
            self.transform_group.setVisible(False)
            if self._module_browser_enabled:
                self._populate_module_meshes([])
            self._update_character_mode_badge(None)
            self._suppress_mode_signal = True
            try:
                self.character_mode_combo.setCurrentIndex(0)
            finally:
                self._suppress_mode_signal = False
            return
        self._current_model = model
        # A model view is not a single node; the per-node transform editor
        # only applies to a concrete selection.
        self.transform_group.setVisible(False)
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
        if self._module_browser_enabled:
            module_mesh_nodes = self._module_mesh_candidates(model, mesh_nodes, all_nodes)
            self._populate_module_meshes(module_mesh_nodes)

    def show_scene_object(self, obj) -> None:
        self._current_node = None
        self.transform_group.setVisible(False)
        transform = getattr(obj, "transform", None)
        source = getattr(obj, "source_ref", None)
        runtime_model = (getattr(obj, "metadata", {}) or {}).get("_runtime_model")
        position = getattr(transform, "position", (0.0, 0.0, 0.0))
        rotation = getattr(transform, "rotation", (0.0, 0.0, 0.0))
        scale = getattr(transform, "scale", (1.0, 1.0, 1.0))
        if transform is not None:
            self.x_spin.setValue(self.unit_system.to_display_units(float(position[0])))
            self.y_spin.setValue(self.unit_system.to_display_units(float(position[1])))
            self.z_spin.setValue(self.unit_system.to_display_units(float(position[2])))
        lines = [
            f"Scene Object: {getattr(obj, 'name', '')}",
            f"Type: {getattr(obj, 'object_type', '')}",
            f"Visible: {getattr(obj, 'visible', True)}",
            f"Locked: {getattr(obj, 'locked', False)}",
            "",
            "-- Source --",
            f"Game: {getattr(source, 'game', '') if source else ''}",
            f"Resref: {getattr(source, 'resref', '') if source else ''}",
            f"Path: {getattr(source, 'source_path', '') if source else ''}",
            "",
            "-- Transform --",
            f"Position: {position[0]:.3f}, {position[1]:.3f}, {position[2]:.3f}",
            f"Rotation: {rotation[0]:.3f}, {rotation[1]:.3f}, {rotation[2]:.3f}",
            f"Scale: {scale[0]:.3f}, {scale[1]:.3f}, {scale[2]:.3f}",
        ]
        stats = self._scene_object_runtime_stats(runtime_model, scale)
        if stats:
            formatter = MeasurementFormatter(self.unit_system, self.measurement_settings.distance_precision)
            lines += [
                "",
                "-- Geometry --",
                f"Nodes: {stats['nodes']:,}",
                f"Meshes: {stats['meshes']:,}",
                f"Verts: {stats['verts']:,}",
                f"Faces: {stats['faces']:,}",
            ]
            size = stats.get("size")
            if size is not None:
                lines += [
                    "",
                    "-- Dimensions --",
                    f"Width:  {formatter.distance(size[0])}",
                    f"Depth:  {formatter.distance(size[1])}",
                    f"Height: {formatter.distance(size[2])}",
                ]
        self.text.setPlainText("\n".join(lines))

    def _scene_object_runtime_stats(self, model, scale) -> dict | None:
        if model is None:
            return None
        try:
            mesh_nodes = list(model.mesh_nodes()) if hasattr(model, "mesh_nodes") else []
        except Exception:
            mesh_nodes = []
        try:
            all_nodes = list(model.all_nodes()) if hasattr(model, "all_nodes") else []
        except Exception:
            all_nodes = []
        verts = sum(len(getattr(node, "vertices", []) or []) for node in mesh_nodes)
        faces = sum(len(getattr(node, "faces", []) or []) for node in mesh_nodes)
        size = None
        try:
            if hasattr(model, "compute_bounds"):
                model.compute_bounds()
            bb_min = tuple(float(v) for v in getattr(model, "bb_min")[:3])
            bb_max = tuple(float(v) for v in getattr(model, "bb_max")[:3])
            sx, sy, sz = (abs(float(v)) for v in tuple(scale or (1.0, 1.0, 1.0))[:3])
            size = (
                max(0.0, bb_max[0] - bb_min[0]) * sx,
                max(0.0, bb_max[1] - bb_min[1]) * sy,
                max(0.0, bb_max[2] - bb_min[2]) * sz,
            )
        except Exception:
            size = None
        return {
            "nodes": len(all_nodes),
            "meshes": len(mesh_nodes),
            "verts": verts,
            "faces": faces,
            "size": size,
        }

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
        self.x_spin.setValue(self.unit_system.to_display_units(float(pos[0])))
        self.y_spin.setValue(self.unit_system.to_display_units(float(pos[1])))
        self.z_spin.setValue(self.unit_system.to_display_units(float(pos[2])))
        # Populate the rotation spin boxes from the node quaternion using the
        # shared camera_math helper (consistent ZYX Euler convention).
        rot_deg = quat_to_euler_degrees(rot)
        self.rx_spin.setValue(float(rot_deg[0]))
        self.ry_spin.setValue(float(rot_deg[1]))
        self.rz_spin.setValue(float(rot_deg[2]))
        formatter = MeasurementFormatter(self.unit_system, self.measurement_settings.distance_precision)
        dimensions = self.dimension_calculator.calculate(node)
        # Populate scale spin boxes; suppress the uniform-scale handler while
        # bulk-setting so we don't cascade.
        self._suppress_scale_signal = True
        try:
            self.sx_spin.setValue(float(dimensions.scale[0]))
            self.sy_spin.setValue(float(dimensions.scale[1]))
            self.sz_spin.setValue(float(dimensions.scale[2]))
        finally:
            self._suppress_scale_signal = False
        # The transform editor is only meaningful for a concrete node.
        self.transform_group.setVisible(True)
        lines = [
            f"Node:  {getattr(node, 'name', '')}",
            f"Type:  {getattr(node, 'type_label', '')}",
            "",
            "-- Position --",
            f"X: {formatter.distance(dimensions.position[0])}",
            f"Y: {formatter.distance(dimensions.position[1])}",
            f"Z: {formatter.distance(dimensions.position[2])}",
            "",
            "-- Rotation --",
            f"X: {formatter.angle_degrees(dimensions.rotation_degrees[0])}",
            f"Y: {formatter.angle_degrees(dimensions.rotation_degrees[1])}",
            f"Z: {formatter.angle_degrees(dimensions.rotation_degrees[2])}",
            "",
            "-- Scale --",
            f"X: {formatter.scale(dimensions.scale[0])}",
            f"Y: {formatter.scale(dimensions.scale[1])}",
            f"Z: {formatter.scale(dimensions.scale[2])}",
            f"Rot:   ({rot[0]:.3f}, {rot[1]:.3f}, {rot[2]:.3f}, {rot[3]:.3f})",
        ]
        if self.measurement_settings.show_selected_object_dimensions:
            lines += [
                "",
                "-- Dimensions --",
            ]
            if dimensions.size is None:
                lines.append("Unavailable")
            else:
                lines.extend(
                    [
                        f"Width:  {formatter.distance(dimensions.size[0])}",
                        f"Depth:  {formatter.distance(dimensions.size[1])}",
                        f"Height: {formatter.distance(dimensions.size[2])}",
                    ]
                )
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

    def _is_null_mesh_candidate(self, node) -> bool:
        texture = str(getattr(node, "texture", "") or "").strip().lower()
        return texture in {"", "null", "none", "****"}

    def _is_wall_mesh_candidate(self, node) -> bool:
        texture = str(getattr(node, "texture", "") or "").strip().lower()
        texture = texture.rsplit(".", 1)[0] if "." in texture else texture
        return texture == "lhr_wall07"

    def _module_mesh_candidates(self, model, mesh_nodes=None, all_nodes=None) -> list:
        candidates = []
        seen = set()
        extra_nodes = getattr(model, "_gr_extra_module_mesh_nodes", []) or []
        for source in (mesh_nodes or [], all_nodes or [], extra_nodes):
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
        if not self._module_browser_enabled:
            return
        self._suppress_mesh_signal = True
        auto_hidden_changed = False
        try:
            self.module_mesh_tree.clear()
            self.module_wall_mesh_tree.clear()
            self.module_walkmesh_tree.clear()
            self.module_null_mesh_tree.clear()
            self._mesh_items.clear()
            self._wall_items.clear()
            self._walkmesh_items.clear()
            self._null_mesh_items.clear()
            for node in mesh_nodes or []:
                if not self._is_module_mesh_candidate(node):
                    continue
                verts = len(getattr(node, "vertices", []) or [])
                faces = len(getattr(node, "faces", []) or [])
                texture = str(getattr(node, "texture", "") or "")
                if self._is_wall_mesh_candidate(node) and not bool(getattr(node, "_gr_hidden", False)):
                    setattr(node, "_gr_hidden", True)
                    auto_hidden_changed = True
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
                        item.setForeground(column, QtGui.QBrush(QtGui.QColor(self._color("text.secondary", "text2"))))
                if self._is_wall_mesh_candidate(node):
                    tree = self.module_wall_mesh_tree
                    items = self._wall_items
                elif self._is_walkmesh_candidate(node):
                    tree = self.module_walkmesh_tree
                    items = self._walkmesh_items
                elif self._is_null_mesh_candidate(node):
                    tree = self.module_null_mesh_tree
                    items = self._null_mesh_items
                else:
                    tree = self.module_mesh_tree
                    items = self._mesh_items
                tree.addTopLevelItem(item)
                items[item] = node
            for tree in (self.module_mesh_tree, self.module_wall_mesh_tree, self.module_null_mesh_tree, self.module_walkmesh_tree):
                for column in range(tree.columnCount()):
                    tree.resizeColumnToContents(column)
            count = self.module_mesh_tree.topLevelItemCount()
            self.module_mesh_count.setText(f"{count:,} module mesh(es)" if count else "No module meshes.")
            wall_count = self.module_wall_mesh_tree.topLevelItemCount()
            self.module_wall_mesh_count.setText(f"{wall_count:,} wall(s)" if wall_count else "No walls.")
            null_count = self.module_null_mesh_tree.topLevelItemCount()
            self.module_null_mesh_count.setText(f"{null_count:,} NULL mesh(es)" if null_count else "No NULL meshes.")
            walk_count = self.module_walkmesh_tree.topLevelItemCount()
            self.module_walkmesh_count.setText(f"{walk_count:,} walkmesh(es)" if walk_count else "No walkmeshes.")
        finally:
            self._suppress_mesh_signal = False
        if auto_hidden_changed:
            self.moduleMeshVisibilityChanged.emit()

    def _filter_module_meshes(self, text: str) -> None:
        if not self._module_browser_enabled:
            return
        for edit, items in (
            (self.module_mesh_filter, self._mesh_items),
            (self.module_wall_mesh_filter, self._wall_items),
            (self.module_null_mesh_filter, self._null_mesh_items),
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
        if not self._module_browser_enabled:
            return []
        selected = []
        for tree, items in (
            (self.module_mesh_tree, self._mesh_items),
            (self.module_wall_mesh_tree, self._wall_items),
            (self.module_null_mesh_tree, self._null_mesh_items),
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

    def _on_module_mesh_item_clicked(self, item: QtWidgets.QTreeWidgetItem, _column: int) -> None:
        if self._suppress_mesh_signal or item is None:
            return
        nodes = self._selected_module_meshes()
        if not nodes:
            for items in (self._mesh_items, self._wall_items, self._null_mesh_items, self._walkmesh_items):
                node = items.get(item)
                if node is not None:
                    nodes = [node]
                    break
        if not nodes:
            return
        self.moduleMeshesSelected.emit(nodes)
        self.moduleMeshSelected.emit(nodes[0])

    def select_module_mesh(self, node) -> None:
        self.select_module_meshes([node] if node is not None else [])

    def has_module_mesh(self, node) -> bool:
        if not self._module_browser_enabled or self.module_tab is None or node is None:
            return False
        if not self._is_module_mesh_candidate(node):
            return False
        node_id = id(node)
        return any(
            id(candidate) == node_id
            for items in (self._mesh_items, self._wall_items, self._null_mesh_items, self._walkmesh_items)
            for candidate in items.values()
        )

    def select_module_meshes(self, nodes: list) -> bool:
        if not self._module_browser_enabled or self.module_tab is None or self._suppress_mesh_signal:
            return False
        node_ids = {id(node) for node in nodes if node is not None and self._is_module_mesh_candidate(node)}
        selected_any = False
        self._suppress_mesh_signal = True
        try:
            self.module_mesh_tree.clearSelection()
            self.module_wall_mesh_tree.clearSelection()
            self.module_null_mesh_tree.clearSelection()
            self.module_walkmesh_tree.clearSelection()
            if not node_ids:
                return False
            for tree, items, tab in (
                (self.module_mesh_tree, self._mesh_items, 0),
                (self.module_wall_mesh_tree, self._wall_items, 1),
                (self.module_null_mesh_tree, self._null_mesh_items, 2),
                (self.module_walkmesh_tree, self._walkmesh_items, 3),
            ):
                for item, candidate in items.items():
                    if id(candidate) in node_ids:
                        item.setSelected(True)
                        tree.setCurrentItem(item)
                        tree.scrollToItem(item, QtWidgets.QAbstractItemView.PositionAtCenter)
                        self.module_browser_tabs.setCurrentIndex(tab)
                        selected_any = True
            self.tabs.setCurrentWidget(self.module_tab)
            return selected_any
        finally:
            self._suppress_mesh_signal = False

    def select_module_mesh_by_label(self, label: str):
        if not self._module_browser_enabled or self.module_tab is None or self._suppress_mesh_signal:
            return None
        needle = str(label or "").strip().lower()
        if not needle:
            return None
        self._suppress_mesh_signal = True
        try:
            self.module_mesh_tree.clearSelection()
            self.module_wall_mesh_tree.clearSelection()
            self.module_null_mesh_tree.clearSelection()
            self.module_walkmesh_tree.clearSelection()
            for tree, items, tab in (
                (self.module_mesh_tree, self._mesh_items, 0),
                (self.module_wall_mesh_tree, self._wall_items, 1),
                (self.module_null_mesh_tree, self._null_mesh_items, 2),
                (self.module_walkmesh_tree, self._walkmesh_items, 3),
            ):
                for item, node in items.items():
                    labels = {
                        item.text(0),
                        self._mesh_label(node),
                        str(getattr(node, "name", "") or ""),
                        str(getattr(node, "node_name", "") or ""),
                    }
                    if needle not in {candidate.lower() for candidate in labels if candidate}:
                        continue
                    item.setSelected(True)
                    tree.setCurrentItem(item)
                    tree.scrollToItem(item, QtWidgets.QAbstractItemView.PositionAtCenter)
                    self.module_browser_tabs.setCurrentIndex(tab)
                    self.tabs.setCurrentWidget(self.module_tab)
                    return node
        finally:
            self._suppress_mesh_signal = False
        return None

    def select_all_module_meshes(self) -> None:
        if not self._module_browser_enabled:
            return
        if self.module_browser_tabs.currentWidget() is self.module_browser_tabs.widget(1):
            self.module_wall_mesh_tree.selectAll()
        elif self.module_browser_tabs.currentWidget() is self.module_browser_tabs.widget(2):
            self.module_null_mesh_tree.selectAll()
        elif self.module_browser_tabs.currentWidget() is self.module_browser_tabs.widget(3):
            self.module_walkmesh_tree.selectAll()
        else:
            self.module_mesh_tree.selectAll()

    def _refresh_module_mesh_rows(self) -> None:
        if not self._module_browser_enabled:
            return
        for tree, items in (
            (self.module_mesh_tree, self._mesh_items),
            (self.module_wall_mesh_tree, self._wall_items),
            (self.module_null_mesh_tree, self._null_mesh_items),
            (self.module_walkmesh_tree, self._walkmesh_items),
        ):
            for item, node in items.items():
                hidden = bool(getattr(node, "_gr_hidden", False))
                item.setText(4, "no" if hidden else "yes")
                item.setText(5, str(getattr(node, "_gr_mesh_group", "") or ""))
                brush = QtGui.QBrush(QtGui.QColor(self._color("text.secondary", "text2") if hidden else self._color("text.primary", "text")))
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
            for node in (
                list(self._mesh_items.values())
                + list(self._wall_items.values())
                + list(self._null_mesh_items.values())
                + list(self._walkmesh_items.values())
            )
            if id(node) not in selected
        ]
        self._set_meshes_hidden(nodes, True)

    def _unhide_all_module_meshes(self) -> None:
        self._set_meshes_hidden(
            list(self._mesh_items.values())
            + list(self._wall_items.values())
            + list(self._null_mesh_items.values())
            + list(self._walkmesh_items.values()),
            False,
        )

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
