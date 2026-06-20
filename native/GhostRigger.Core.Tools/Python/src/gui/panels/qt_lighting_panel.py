"""Dockable professional lighting controls for the Qt viewport."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.gui.libtheme.collapsible_group import CollapsibleGroupBox
from src.gui.qt_lib.assets import qt_icon_manager
from src.core.lighting.light_manager import LightManager
from src.core.lighting.light_model import GhostRiggerLight
from src.core.lighting.light_types import (
    LightType,
    LightingRigPreset,
    LightmapMode,
    SceneLightingMode,
    ShaderComplexityMode,
)
from src.core.lighting.lighting_rig_presets import LightingRigPresets
from src.core.lighting.settings import LightingSettings, LightingSettingsStore


class QtLightingPanel(QtWidgets.QWidget):
    lightingModeChanged = QtCore.Signal(str)
    mapToggled = QtCore.Signal(str, bool)
    lightmapSettingsChanged = QtCore.Signal(float, str)
    shaderComplexityChanged = QtCore.Signal(str)
    helperVisibilityChanged = QtCore.Signal(bool, bool)
    lightChanged = QtCore.Signal()
    lightSelected = QtCore.Signal(object)
    createLightRequested = QtCore.Signal(str)
    lightmapBakeRequested = QtCore.Signal()

    _TYPE_LABELS = ("Point", "Spot", "Directional", "Area", "Ambient", "AuroraPoint", "AuroraAmbient", "AuroraUnknown")
    _TYPE_VALUES = ("point", "spot", "directional", "area", "ambient", "aurora_point", "aurora_ambient", "aurora_unknown")
    _COLUMNS = ("Enabled", "Color", "Name", "Type", "Radius", "Intensity", "Cone", "Group", "Visible", "Locked", "Source")
    _LIGHTING_MODE_ICONS = {
        "scene": qt_icon_manager.I.LIGHTING_MODE_SCENE,
        "unlit": qt_icon_manager.I.LIGHTING_MODE_UNLIT,
        "fullbright": qt_icon_manager.I.LIGHTING_MODE_FULLBRIGHT,
        "lightmap_preview": qt_icon_manager.I.LIGHTING_MODE_LIGHTMAP,
        "diffuse_only": qt_icon_manager.I.LIGHTING_MODE_DIFFUSE,
        "normal_only": qt_icon_manager.I.LIGHTING_MODE_NORMAL,
        "specular_only": qt_icon_manager.I.LIGHTING_MODE_SPECULAR,
        "environment_only": qt_icon_manager.I.LIGHTING_MODE_ENVIRONMENT,
        "shader_complexity": qt_icon_manager.I.LIGHTING_MODE_SHADER,
        "photoreal_preview": qt_icon_manager.I.LIGHTING_MODE_PHOTOREAL,
    }
    _COMPLEXITY_ICONS = {
        "off": qt_icon_manager.I.LIGHTING_COMPLEXITY_OFF,
        "basic": qt_icon_manager.I.LIGHTING_COMPLEXITY_BASIC,
        "overdraw": qt_icon_manager.I.LIGHTING_COMPLEXITY_OVERDRAW,
        "texture_cost": qt_icon_manager.I.LIGHTING_COMPLEXITY_TEXTURE,
        "lighting_cost": qt_icon_manager.I.LIGHTING_COMPLEXITY_LIGHTING,
        "full_complexity": qt_icon_manager.I.LIGHTING_COMPLEXITY_FULL,
    }
    _RIG_ICONS = {
        "none": qt_icon_manager.I.LIGHTING_RIG_NONE,
        "kotor_original": qt_icon_manager.I.LIGHTING_RIG_KOTOR,
        "neutral_studio": qt_icon_manager.I.LIGHTING_RIG_NEUTRAL,
        "cinematic_warm": qt_icon_manager.I.LIGHTING_RIG_WARM,
        "cinematic_cold": qt_icon_manager.I.LIGHTING_RIG_COLD,
        "interior_torch": qt_icon_manager.I.LIGHTING_RIG_TORCH,
        "exterior_moonlight": qt_icon_manager.I.LIGHTING_RIG_MOON,
        "photoreal_softbox": qt_icon_manager.I.LIGHTING_RIG_SOFTBOX,
        "unreal_preview": qt_icon_manager.I.LIGHTING_RIG_UNREAL,
        "max_style_preview": qt_icon_manager.I.LIGHTING_RIG_MAX,
    }

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.manager = LightManager()
        self._model = None
        self._lights: list[object] = []
        self._selected = None
        self._updating = False
        self._settings_store = LightingSettingsStore()
        self._settings = self._settings_store.load()
        self._icons = {
            "point": qt_icon_manager.get(qt_icon_manager.I.LIGHT_POINT, 16),
            "aurora_point": qt_icon_manager.get(qt_icon_manager.I.LIGHT_POINT, 16),
            "spot": qt_icon_manager.get(qt_icon_manager.I.LIGHT_SPOT, 16),
            "directional": qt_icon_manager.get(qt_icon_manager.I.LIGHT_DIRECTIONAL, 16),
            "area": qt_icon_manager.get(qt_icon_manager.I.LIGHT_AREA, 16),
            "ambient": qt_icon_manager.get(qt_icon_manager.I.LIGHT_AMBIENT, 16),
            "aurora_ambient": qt_icon_manager.get(qt_icon_manager.I.LIGHT_AMBIENT, 16),
            "aurora_unknown": qt_icon_manager.get(qt_icon_manager.I.LIGHTS, 16),
        }
        self._build()
        self._load_settings_into_ui()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(7)

        create_group = QtWidgets.QGroupBox("Add Light to Scene")
        create_group.setObjectName("AddLightToSceneGroup")
        create_row = QtWidgets.QGridLayout(create_group)
        create_row.setContentsMargins(6, 8, 6, 6)
        create_row.setHorizontalSpacing(4)
        create_row.setVerticalSpacing(4)
        for column, (label, light_type, icon_name) in enumerate((
            ("Point", "point", qt_icon_manager.I.LIGHT_POINT),
            ("Spot", "spot", qt_icon_manager.I.LIGHT_SPOT),
            ("Directional", "directional", qt_icon_manager.I.LIGHT_DIRECTIONAL),
            ("Area", "area", qt_icon_manager.I.LIGHT_AREA),
            ("Ambient", "ambient", qt_icon_manager.I.LIGHT_AMBIENT),
        )):
            button = self._tool_button(icon_name, f"Create {label} light")
            button.setToolTip(f"Create {label} light")
            button.clicked.connect(lambda _checked=False, t=light_type: self.createLightRequested.emit(t))
            create_row.addWidget(button, 0, column)
        root.addWidget(create_group)

        lighting_group = QtWidgets.QGroupBox("Lighting System")
        lighting_group.setObjectName("LightingSystemGroup")
        lighting_grid = QtWidgets.QGridLayout(lighting_group)
        lighting_grid.setContentsMargins(6, 8, 6, 6)
        lighting_grid.setHorizontalSpacing(5)
        lighting_grid.setVerticalSpacing(5)
        self.mode_combo = QtWidgets.QComboBox()
        for mode in SceneLightingMode:
            self.mode_combo.addItem(mode.label, mode.value)
        self.mode_combo.currentIndexChanged.connect(lambda _index=0: self._emit_mode())
        self.mode_combo.hide()

        self.shader_complexity_combo = QtWidgets.QComboBox()
        for mode in ShaderComplexityMode:
            self.shader_complexity_combo.addItem(mode.label, mode.value)
        self.shader_complexity_combo.currentIndexChanged.connect(lambda _index=0: self._emit_shader_complexity())
        self.shader_complexity_combo.hide()

        self.rig_preset_combo = QtWidgets.QComboBox()
        for preset in LightingRigPreset:
            self.rig_preset_combo.addItem(preset.label, preset.value)
        self.rig_preset_combo.currentIndexChanged.connect(lambda _index=0: self._apply_rig_preset())
        self.rig_preset_combo.hide()
        self.mode_buttons: dict[str, QtWidgets.QToolButton] = {}
        self.shader_complexity_buttons: dict[str, QtWidgets.QToolButton] = {}
        self.rig_preset_buttons: dict[str, QtWidgets.QToolButton] = {}
        row = 0
        row = self._add_button_grid(
            lighting_grid,
            row,
            "Scene Lighting Modes",
            [(mode.value, mode.label, self._LIGHTING_MODE_ICONS.get(mode.value, qt_icon_manager.I.LIGHTS)) for mode in SceneLightingMode],
            self.mode_buttons,
            self._select_lighting_mode,
            columns=10,
        )
        row = self._add_button_grid(
            lighting_grid,
            row,
            "Lighting Complexity",
            [(mode.value, mode.label, self._COMPLEXITY_ICONS.get(mode.value, qt_icon_manager.I.LIGHTS)) for mode in ShaderComplexityMode],
            self.shader_complexity_buttons,
            self._select_shader_complexity,
            columns=6,
        )
        self._add_button_grid(
            lighting_grid,
            row,
            "Lighting Rigs",
            [(preset.value, preset.label, self._RIG_ICONS.get(preset.value, qt_icon_manager.I.RIG)) for preset in LightingRigPreset],
            self.rig_preset_buttons,
            self._select_rig_preset,
            columns=10,
        )
        lighting_grid.addWidget(self.mode_combo, lighting_grid.rowCount(), 0)
        lighting_grid.addWidget(self.shader_complexity_combo, lighting_grid.rowCount(), 0)
        lighting_grid.addWidget(self.rig_preset_combo, lighting_grid.rowCount(), 0)
        root.addWidget(lighting_group)

        maps = CollapsibleGroupBox("Preview")
        maps_layout = QtWidgets.QGridLayout(maps)
        maps_layout.setContentsMargins(8, 8, 8, 8)
        maps_layout.setHorizontalSpacing(10)
        maps_layout.setVerticalSpacing(4)
        maps_layout.addWidget(QtWidgets.QLabel("Texture Maps:"), 0, 0, 1, 3)
        self.map_checks: dict[str, QtWidgets.QCheckBox] = {}
        for idx, (key, label) in enumerate((
            ("diffuse", "Diffuse"),
            ("normal", "Normal"),
            ("environment", "Environment"),
            ("specular", "Specular"),
            ("lightmap", "Lightmap"),
        )):
            check = QtWidgets.QCheckBox(label)
            check.setChecked(True)
            check.toggled.connect(lambda state, k=key: self._emit_map(k, state))
            self.map_checks[key] = check
            maps_layout.addWidget(check, 1 + (idx // 3), idx % 3)
        maps_layout.addWidget(QtWidgets.QLabel("LM Intensity"), 3, 0)
        self.lightmap_intensity_spin = QtWidgets.QDoubleSpinBox()
        self.lightmap_intensity_spin.setRange(0.0, 4.0)
        self.lightmap_intensity_spin.setDecimals(2)
        self.lightmap_intensity_spin.setSingleStep(0.05)
        self.lightmap_intensity_spin.setValue(0.55)
        self.lightmap_intensity_spin.setMaximumWidth(96)
        self.lightmap_intensity_spin.valueChanged.connect(lambda _value=0.0: self._emit_lightmap_settings())
        maps_layout.addWidget(self.lightmap_intensity_spin, 3, 1)
        maps_layout.addWidget(QtWidgets.QLabel("LM Mode"), 4, 0)
        self.lightmap_mode_combo = QtWidgets.QComboBox()
        for mode in LightmapMode:
            self.lightmap_mode_combo.addItem(mode.label, mode.value)
        self.lightmap_mode_combo.currentIndexChanged.connect(lambda _index=0: self._emit_lightmap_settings())
        maps_layout.addWidget(self.lightmap_mode_combo, 4, 1, 1, 2)
        root.addWidget(maps)

        bake_row = QtWidgets.QHBoxLayout()
        self.bake_lightmaps_button = QtWidgets.QPushButton("Bake Lightmaps...")
        self.bake_lightmaps_button.setToolTip("Generate replacement lightmap textures from the current scene lighting.")
        self.bake_lightmaps_button.clicked.connect(self.lightmapBakeRequested.emit)
        bake_row.addWidget(self.bake_lightmaps_button)
        bake_row.addStretch(1)
        root.addLayout(bake_row)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(list(self._COLUMNS))
        self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.tree.setIconSize(QtCore.QSize(16, 16))
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree.itemSelectionChanged.connect(self._on_tree_selection)
        self.tree.itemClicked.connect(self._on_tree_item_clicked)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemDoubleClicked.connect(lambda item, _col=0: self.lightSelected.emit(item.data(0, QtCore.Qt.UserRole)))
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.setMinimumHeight(190)
        for index, width in enumerate((70, 42, 150, 92, 72, 72, 58, 82, 58, 58, 82)):
            self.tree.setColumnWidth(index, width)
        root.addWidget(self.tree, 1)

        editor = CollapsibleGroupBox("Selected Light")
        editor_layout = QtWidgets.QGridLayout(editor)
        editor_layout.setContentsMargins(8, 8, 8, 8)
        editor_layout.setHorizontalSpacing(6)
        editor_layout.setVerticalSpacing(5)
        flags_row = QtWidgets.QHBoxLayout()
        flags_row.setSpacing(8)
        self.enabled_check = QtWidgets.QCheckBox("Enabled")
        self.enabled_check.toggled.connect(lambda _state=False: self._apply_editor())
        flags_row.addWidget(self.enabled_check)
        self.ambient_check = QtWidgets.QCheckBox("Ambient only")
        self.ambient_check.toggled.connect(lambda _state=False: self._apply_editor())
        flags_row.addWidget(self.ambient_check)
        self.shadow_check = QtWidgets.QCheckBox("Cast shadows")
        self.shadow_check.toggled.connect(lambda _state=False: self._apply_editor())
        flags_row.addWidget(self.shadow_check)
        flags_row.addStretch(1)
        editor_layout.addLayout(flags_row, 0, 0, 1, 6)
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.editingFinished.connect(self._apply_editor)
        editor_layout.addWidget(QtWidgets.QLabel("Name"), 1, 0)
        editor_layout.addWidget(self.name_edit, 1, 1)
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItems(self._TYPE_LABELS)
        self.type_combo.currentIndexChanged.connect(lambda _index=0: self._apply_editor())
        self.type_combo.setMaximumWidth(150)
        editor_layout.addWidget(QtWidgets.QLabel("Type"), 1, 2)
        editor_layout.addWidget(self.type_combo, 1, 3)
        self.color_button = QtWidgets.QPushButton()
        self.color_button.setFixedHeight(20)
        self.color_button.setMaximumWidth(86)
        self.color_button.clicked.connect(self._choose_color)
        editor_layout.addWidget(QtWidgets.QLabel("Color"), 1, 4)
        editor_layout.addWidget(self.color_button, 1, 5)
        self.radius_spin = self._double_spin(0.01, 500.0, 0.25, 2)
        self.intensity_spin = self._double_spin(0.0, 100.0, 0.1, 2)
        self.cone_spin = self._double_spin(1.0, 179.0, 1.0, 1)
        self.area_spin = self._double_spin(0.0, 100.0, 0.1, 2)
        for spin in (self.radius_spin, self.intensity_spin, self.cone_spin, self.area_spin):
            spin.setMaximumWidth(90)
        for column, (label, spin) in enumerate((
            ("Radius", self.radius_spin),
            ("Intensity", self.intensity_spin),
            ("Cone", self.cone_spin),
            ("Area", self.area_spin),
        )):
            editor_layout.addWidget(QtWidgets.QLabel(label), 2, column * 2)
            editor_layout.addWidget(spin, 2, column * 2 + 1)
        affects = QtWidgets.QHBoxLayout()
        affects.setSpacing(8)
        self.affect_diffuse_check = QtWidgets.QCheckBox("Diffuse")
        self.affect_specular_check = QtWidgets.QCheckBox("Specular")
        self.affect_lightmap_check = QtWidgets.QCheckBox("Lightmap")
        self.affect_environment_check = QtWidgets.QCheckBox("Env")
        for check in (self.affect_diffuse_check, self.affect_specular_check, self.affect_lightmap_check, self.affect_environment_check):
            check.toggled.connect(lambda _state=False: self._apply_editor())
            affects.addWidget(check)
        affects.addStretch(1)
        editor_layout.addWidget(QtWidgets.QLabel("Affects"), 3, 0)
        editor_layout.addLayout(affects, 3, 1, 1, 5)
        self.pos_spins: list[QtWidgets.QDoubleSpinBox] = []
        self.rot_spins: list[QtWidgets.QDoubleSpinBox] = []
        self.group_edit = QtWidgets.QLineEdit()
        self.group_edit.editingFinished.connect(self._apply_group_name)
        editor_layout.addWidget(QtWidgets.QLabel("Group"), 4, 0)
        editor_layout.addWidget(self.group_edit, 4, 1, 1, 5)
        root.addWidget(editor)

        self._set_editor_enabled(False)

    def apply_ghost_theme(self, theme) -> None:
        self.setStyleSheet(
            f"QWidget {{ color:{theme.color('text.primary')}; }}"
            f"QGroupBox {{ color:{theme.color('groupbox.title')}; border:1px solid {theme.color('groupbox.border')}; margin-top:8px; padding-top:7px; }}"
            "QGroupBox::title { subcontrol-origin:margin; left:6px; padding:0 4px; }"
            f"QTreeWidget, QComboBox, QDoubleSpinBox, QLineEdit {{ background:{theme.color('input.background')}; color:{theme.color('input.text')}; border:1px solid {theme.color('input.border')}; }}"
            f"QTreeWidget::item:selected {{ background:{theme.color('selection.background')}; color:{theme.color('selection.text')}; }}"
            f"QHeaderView::section {{ background:{theme.color('table.headerBackground')}; color:{theme.color('table.headerText')}; border:1px solid {theme.color('table.grid', theme.color('panel.border'))}; padding:3px; }}"
            f"QCheckBox {{ color:{theme.color('text.primary')}; }}"
            f"QPushButton {{ background:{theme.color('button.background')}; color:{theme.color('button.text')}; border:1px solid {theme.color('panel.border')}; padding:1px 6px; min-height:{theme.metric('button.height', 16)}px; min-width:{theme.metric('button.minWidth', 64)}px; }}"
            f"QPushButton:hover {{ background:{theme.color('button.hover')}; }}"
            f"QPushButton:checked {{ background:{theme.color('button.checked')}; color:{theme.color('button.checkedText', theme.color('button.accentText'))}; }}"
            f"QToolButton {{ background:{theme.color('button.background')}; border:1px solid {theme.color('panel.border')}; padding:1px; }}"
            f"QToolButton:hover {{ background:{theme.color('button.hover')}; }}"
            f"QToolButton:checked {{ background:{theme.color('button.checked')}; }}"
        )
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
        widgets = [
            *self.findChildren(QtWidgets.QComboBox),
            *self.findChildren(QtWidgets.QDoubleSpinBox),
            *self.findChildren(QtWidgets.QLineEdit),
        ]
        for widget in widgets:
            widget.setMinimumHeight(layout.spacing_value("inputHeight", 24))

    def _double_spin(self, minimum: float, maximum: float, step: float, decimals: int) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setSingleStep(step)
        spin.valueChanged.connect(lambda _value=0.0: self._apply_editor())
        return spin

    def _tool_button(self, icon_name: str, tooltip: str, *, checkable: bool = False) -> QtWidgets.QToolButton:
        button = QtWidgets.QToolButton()
        button.setIcon(qt_icon_manager.get(icon_name, 18))
        button.setIconSize(QtCore.QSize(18, 18))
        button.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        button.setCheckable(checkable)
        button.setAutoRaise(False)
        button.setFixedSize(28, 24)
        button.setCursor(QtCore.Qt.PointingHandCursor)
        button.setToolTip(tooltip)
        return button

    def _add_button_grid(
        self,
        layout: QtWidgets.QGridLayout,
        row: int,
        title: str,
        items: list[tuple[str, str, str]],
        buttons: dict[str, QtWidgets.QToolButton],
        callback,
        *,
        columns: int,
    ) -> int:
        label = QtWidgets.QLabel(title)
        layout.addWidget(label, row, 0, 1, columns)
        for idx, (value, tooltip, icon_name) in enumerate(items):
            button = self._tool_button(icon_name, tooltip, checkable=True)
            button.clicked.connect(lambda _checked=False, v=value: callback(v))
            buttons[str(value)] = button
            layout.addWidget(button, row + 1 + (idx // columns), idx % columns)
        return row + 2 + max(0, (len(items) - 1) // columns)

    def _sync_button_group(self, buttons: dict[str, QtWidgets.QToolButton], value: str) -> None:
        for key, button in buttons.items():
            with QtCore.QSignalBlocker(button):
                button.setChecked(key == value)

    def _select_lighting_mode(self, mode: str) -> None:
        if self._updating:
            return
        mode = str(mode or "scene")
        self._set_combo_data(self.mode_combo, mode, emit=False)
        self._settings.scene_lighting_mode = mode
        self._sync_button_group(self.mode_buttons, mode)
        self._save_settings()
        self.lightingModeChanged.emit(mode)

    def _select_shader_complexity(self, mode: str) -> None:
        if self._updating:
            return
        mode = str(mode or "off")
        self._set_combo_data(self.shader_complexity_combo, mode, emit=False)
        self._settings.shader_complexity_mode = mode
        self._sync_button_group(self.shader_complexity_buttons, mode)
        self._save_settings()
        self.shaderComplexityChanged.emit(mode)

    def _select_rig_preset(self, preset: str) -> None:
        if self._updating:
            return
        preset = str(preset or "none")
        self._set_combo_data(self.rig_preset_combo, preset, emit=False)
        self.manager.remove_generated_rig()
        for light in LightingRigPresets.create(preset):
            self.manager.add_light(light)
        self._settings.selected_lighting_rig_preset = preset
        self._sync_button_group(self.rig_preset_buttons, preset)
        self._save_settings()
        self.refresh()
        self.lightChanged.emit()

    def set_model(self, model) -> None:
        self._model = model
        self.manager.set_model(model)
        self._lights = [light.original_ref for light in self.manager.all_lights()]
        self.refresh()

    def refresh(self) -> None:
        previous = self._selected
        self._updating = True
        self.tree.clear()
        selected_items: list[QtWidgets.QTreeWidgetItem] = []
        for light in self.manager.all_lights():
            item = self._make_item(light)
            self.tree.addTopLevelItem(item)
            if light.original_ref is previous or light.selected:
                selected_items.append(item)
        self._updating = False
        if selected_items:
            self._updating = True
            for item in selected_items:
                item.setSelected(True)
            self.tree.setCurrentItem(selected_items[-1])
            self._updating = False
            self._load_editor(self.manager.selected_lights() or [self.manager.find_by_original(previous)])
        elif self.manager.all_lights() and previous is None:
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
        else:
            self._selected = None
            self._set_editor_enabled(False)

    def _make_item(self, light: GhostRiggerLight) -> QtWidgets.QTreeWidgetItem:
        group = self.manager.grouping.groups.get(light.group_id)
        group_name = group.name if group else ""
        item = QtWidgets.QTreeWidgetItem([
            "",
            "",
            light.name,
            self._type_label(light.type),
            f"{light.radius:.2f}",
            f"{light.intensity:.2f}",
            f"{light.cone_angle:.1f}",
            group_name,
            "Yes" if light.visible else "No",
            "Yes" if light.locked else "No",
            light.source_type,
        ])
        item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
        item.setCheckState(0, QtCore.Qt.Checked if light.enabled else QtCore.Qt.Unchecked)
        item.setIcon(1, self._icons.get(light.type, self._icons["point"]))
        item.setData(0, QtCore.Qt.UserRole, light.original_ref)
        item.setData(0, QtCore.Qt.UserRole + 1, light.id)
        color = QtGui.QColor.fromRgbF(*[max(0.0, min(1.0, float(c))) for c in light.color[:3]])
        item.setBackground(1, QtGui.QBrush(color))
        if not light.enabled or not light.visible:
            muted = QtGui.QBrush(QtGui.QColor("#7a8790"))
            for col in range(self.tree.columnCount()):
                item.setForeground(col, muted)
        return item

    def _type_label(self, type_value: str) -> str:
        for light_type in LightType:
            if light_type.value == type_value:
                return light_type.label
        return str(type_value or "point").title()

    def _light_from_item(self, item: QtWidgets.QTreeWidgetItem | None) -> GhostRiggerLight | None:
        if item is None:
            return None
        return self.manager.get(str(item.data(0, QtCore.Qt.UserRole + 1) or ""))

    def _set_editor_enabled(self, enabled: bool) -> None:
        widgets = [
            self.enabled_check, self.name_edit, self.type_combo, self.color_button,
            self.radius_spin, self.intensity_spin, self.cone_spin, self.area_spin,
            self.ambient_check, self.shadow_check, self.group_edit,
            self.affect_diffuse_check, self.affect_specular_check,
            self.affect_lightmap_check, self.affect_environment_check,
            *self.pos_spins, *self.rot_spins,
        ]
        for widget in widgets:
            widget.setEnabled(enabled)

    def has_light(self, node) -> bool:
        return node is not None and bool(getattr(node, "is_light", False)) and self.manager.find_by_original(node) is not None

    def select_light(self, node) -> bool:
        if node is not None and not bool(getattr(node, "is_light", False)):
            node = None
        light = self.manager.find_by_original(node)
        self.manager.select_single(light.original_ref if light else None)
        self._selected = node if light else None
        was_updating = self._updating
        self._updating = True
        self.tree.clearSelection()
        if light is not None:
            for index in range(self.tree.topLevelItemCount()):
                item = self.tree.topLevelItem(index)
                if item.data(0, QtCore.Qt.UserRole) is node:
                    item.setSelected(True)
                    self.tree.setCurrentItem(item)
                    break
            self._load_editor([light])
        else:
            self._load_editor([])
        self._updating = was_updating
        return light is not None

    def _on_tree_selection(self) -> None:
        if self._updating:
            return
        items = self.tree.selectedItems()
        lights = [self._light_from_item(item) for item in items]
        clean = [light for light in lights if light is not None]
        active = self._light_from_item(self.tree.currentItem()) or (clean[-1] if clean else None)
        self.manager.select_many(clean, active=active)
        self._selected = active.original_ref if active is not None else None
        self._load_editor(clean)
        self.lightSelected.emit(self._selected)

    def _on_tree_item_clicked(self, item: QtWidgets.QTreeWidgetItem, _column: int) -> None:
        if self._updating or item is None:
            return
        light = self._light_from_item(item)
        if light is None:
            return
        if not item.isSelected():
            self.tree.setCurrentItem(item)
            item.setSelected(True)
        self.manager.select_many(self.manager.selected_lights() or [light], active=light)
        self._selected = light.original_ref
        self._load_editor(self.manager.selected_lights() or [light])
        self.lightSelected.emit(self._selected)

    def _on_item_changed(self, item: QtWidgets.QTreeWidgetItem, column: int) -> None:
        if self._updating or column != 0:
            return
        light = self._light_from_item(item)
        if light is None:
            return
        self.manager.apply_to_light(light, enabled=item.checkState(0) == QtCore.Qt.Checked)
        self.lightChanged.emit()

    def _load_editor(self, lights: list[GhostRiggerLight | None]) -> None:
        clean = [light for light in lights if light is not None]
        self._updating = True
        self._set_editor_enabled(bool(clean))
        if not clean:
            self._selected = None
            self._updating = False
            return
        active = self.manager.active_light() or clean[-1]
        self._selected = active.original_ref
        multi = len(clean) > 1
        self.enabled_check.setChecked(all(light.enabled for light in clean))
        self.name_edit.setText("Multiple" if multi else active.name)
        self.type_combo.setCurrentIndex(max(0, self._TYPE_VALUES.index(active.type) if active.type in self._TYPE_VALUES else 0))
        self.radius_spin.setValue(float(active.radius))
        self.intensity_spin.setValue(float(active.intensity))
        self.cone_spin.setValue(float(active.cone_angle))
        self.area_spin.setValue(float(active.area_size))
        self.ambient_check.setChecked(bool(active.ambient_only))
        self.shadow_check.setChecked(bool(active.casts_shadows))
        self.affect_diffuse_check.setChecked(bool(active.affects_diffuse))
        self.affect_specular_check.setChecked(bool(active.affects_specular))
        self.affect_lightmap_check.setChecked(bool(active.affects_lightmap))
        self.affect_environment_check.setChecked(bool(active.affects_environment))
        self._set_rotation_editor(active.rotation)
        group = self.manager.grouping.groups.get(active.group_id)
        self.group_edit.setText(group.name if group else "")
        self._set_color_button(active.color)
        self._updating = False

    def _set_rotation_editor(self, quat: tuple[float, float, float, float]) -> None:
        for spin in self.rot_spins:
            spin.setValue(0.0)

    def _apply_editor(self) -> None:
        if self._updating:
            return
        selected = self.manager.selected_lights()
        if not selected:
            return
        changes = {
            "enabled": self.enabled_check.isChecked(),
            "type": self._TYPE_VALUES[self.type_combo.currentIndex()],
            "radius": float(self.radius_spin.value()),
            "intensity": float(self.intensity_spin.value()),
            "cone_angle": float(self.cone_spin.value()),
            "area_size": float(self.area_spin.value()),
            "ambient_only": bool(self.ambient_check.isChecked()),
            "casts_shadows": bool(self.shadow_check.isChecked()),
            "affects_diffuse": bool(self.affect_diffuse_check.isChecked()),
            "affects_specular": bool(self.affect_specular_check.isChecked()),
            "affects_lightmap": bool(self.affect_lightmap_check.isChecked()),
            "affects_environment": bool(self.affect_environment_check.isChecked()),
        }
        if len(selected) == 1 and self.name_edit.text().strip() and self.name_edit.text() != "Multiple":
            changes["name"] = self.name_edit.text().strip()
        self.manager.apply_to_selected(**changes)
        self._selected = self.manager.active_light().original_ref if self.manager.active_light() else None
        self.refresh()
        self.lightChanged.emit()

    def _choose_color(self) -> None:
        active = self.manager.active_light()
        if active is None:
            return
        current = QtGui.QColor.fromRgbF(*active.color)
        color = QtWidgets.QColorDialog.getColor(current, self, "Light Color")
        if not color.isValid():
            return
        rgb = (color.redF(), color.greenF(), color.blueF())
        self.manager.apply_to_selected(color=rgb)
        self._set_color_button(rgb)
        self.refresh()
        self.lightChanged.emit()

    def _set_color_button(self, rgb: tuple[float, float, float]) -> None:
        color = QtGui.QColor.fromRgbF(*[max(0.0, min(1.0, float(c))) for c in rgb[:3]])
        self.color_button.setStyleSheet(f"background:{color.name()}; border:1px solid #52665a;")

    def _apply_group_name(self) -> None:
        active = self.manager.active_light()
        if active is None:
            return
        name = self.group_edit.text().strip()
        if not name:
            self.manager.ungroup_selected()
        elif not active.group_id:
            self.manager.group_selected(name)
        else:
            group = self.manager.grouping.groups.get(active.group_id)
            if group is not None:
                group.name = name
        self.refresh()
        self.lightChanged.emit()

    def _show_context_menu(self, pos: QtCore.QPoint) -> None:
        selected = self.manager.selected_lights()
        menu = QtWidgets.QMenu(self)
        actions = {
            "select": menu.addAction("Select"),
            "add": menu.addAction("Add to Selection"),
        }
        menu.addSeparator()
        actions["isolate"] = menu.addAction("Isolate Selected Lights")
        actions["hide"] = menu.addAction("Hide Selected Lights")
        actions["show"] = menu.addAction("Show Selected Lights")
        actions["lock"] = menu.addAction("Lock Selected Lights")
        actions["unlock"] = menu.addAction("Unlock Selected Lights")
        actions["enable"] = menu.addAction("Enable Selected Lights")
        actions["disable"] = menu.addAction("Disable Selected Lights")
        menu.addSeparator()
        actions["group"] = menu.addAction("Group Selected Lights")
        actions["ungroup"] = menu.addAction("Ungroup Selected Lights")
        actions["rename"] = menu.addAction("Rename Light")
        actions["duplicate"] = menu.addAction("Duplicate Light")
        actions["delete"] = menu.addAction("Delete Light")
        actions["focus"] = menu.addAction("Focus in Viewport")
        for action in actions.values():
            action.setEnabled(bool(selected))
        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen in {actions["select"], actions["focus"]}:
            self.lightSelected.emit(self._selected)
        elif chosen is actions["hide"]:
            self.manager.apply_to_selected(visible=False)
        elif chosen is actions["show"]:
            self.manager.apply_to_selected(visible=True)
        elif chosen is actions["lock"]:
            self.manager.apply_to_selected(locked=True)
        elif chosen is actions["unlock"]:
            self.manager.apply_to_selected(locked=False)
        elif chosen is actions["enable"]:
            self.manager.apply_to_selected(enabled=True)
        elif chosen is actions["disable"]:
            self.manager.apply_to_selected(enabled=False)
        elif chosen is actions["group"]:
            self.manager.group_selected()
        elif chosen is actions["ungroup"]:
            self.manager.ungroup_selected()
        elif chosen is actions["rename"] and len(selected) == 1:
            text, ok = QtWidgets.QInputDialog.getText(self, "Rename Light", "Name", text=selected[0].name)
            if ok and text.strip():
                self.manager.apply_to_light(selected[0], name=text.strip())
        elif chosen is actions["duplicate"]:
            self.manager.duplicate_selected()
        elif chosen is actions["delete"]:
            if any(light.source_type == "Aurora" for light in selected):
                answer = QtWidgets.QMessageBox.question(self, "Delete Source Light", "Disable source AuroraLight records in the scene edit state?")
                if answer != QtWidgets.QMessageBox.Yes:
                    return
            self.manager.soft_delete_selected()
        elif chosen is actions["isolate"]:
            selected_ids = {light.id for light in selected}
            for light in self.manager.all_lights():
                self.manager.apply_to_light(light, visible=light.id in selected_ids)
        self.refresh()
        self.lightChanged.emit()

    def _apply_rig_preset(self) -> None:
        if self._updating:
            return
        preset = str(self.rig_preset_combo.currentData() or "none")
        self._select_rig_preset(preset)

    def _emit_mode(self) -> None:
        if self._updating:
            return
        mode = str(self.mode_combo.currentData() or "scene")
        self._select_lighting_mode(mode)

    def _emit_map(self, key: str, state: bool) -> None:
        setattr(self._settings, f"{key}_map", bool(state))
        self._save_settings()
        self.mapToggled.emit(key, bool(state))

    def _emit_shader_complexity(self) -> None:
        if self._updating:
            return
        mode = str(self.shader_complexity_combo.currentData() or "off")
        self._select_shader_complexity(mode)

    def _emit_helper_visibility(self) -> None:
        helpers = bool(self._settings.show_light_helpers)
        volumes = bool(self._settings.show_light_radius_volumes)
        self._settings.show_light_helpers = helpers
        self._settings.show_light_radius_volumes = volumes
        self._save_settings()
        self.helperVisibilityChanged.emit(helpers, volumes)

    def _emit_lightmap_settings(self) -> None:
        intensity = float(self.lightmap_intensity_spin.value())
        mode = str(self.lightmap_mode_combo.currentData() or "baked")
        self._settings.lightmap_intensity = intensity
        self._settings.lightmap_mode = mode
        self._save_settings()
        self.lightmapSettingsChanged.emit(intensity, mode)

    def _load_settings_into_ui(self) -> None:
        self._updating = True
        self._set_combo_data(self.mode_combo, self._settings.scene_lighting_mode, emit=False)
        self._set_combo_data(self.shader_complexity_combo, self._settings.shader_complexity_mode, emit=False)
        self._set_combo_data(self.rig_preset_combo, self._settings.selected_lighting_rig_preset, emit=False)
        self._sync_button_group(self.mode_buttons, self._settings.scene_lighting_mode)
        self._sync_button_group(self.shader_complexity_buttons, self._settings.shader_complexity_mode)
        self._sync_button_group(self.rig_preset_buttons, self._settings.selected_lighting_rig_preset)
        for key, check in self.map_checks.items():
            check.setChecked(bool(getattr(self._settings, f"{key}_map", True)))
        self.lightmap_intensity_spin.setValue(float(self._settings.lightmap_intensity))
        self._set_combo_data(self.lightmap_mode_combo, self._settings.lightmap_mode, emit=False)
        self._updating = False

    def _set_combo_data(self, combo: QtWidgets.QComboBox, data: str, *, emit: bool = True) -> None:
        idx = combo.findData(data)
        if idx >= 0:
            if emit:
                combo.setCurrentIndex(idx)
            else:
                with QtCore.QSignalBlocker(combo):
                    combo.setCurrentIndex(idx)

    def _save_settings(self) -> None:
        if self._updating:
            return
        self._settings_store.save(self._settings)
