"""Compact, viewport-local controls for Map Studio terrain sculpting."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class TerrainSculptShelf(QtWidgets.QFrame):
    """One readable sculpt shelf that stays next to the terrain viewport.

    The Builder tab still owns terrain creation and advanced heightfield
    operations.  This shelf owns only the high-frequency painting choices a
    user needs while their pointer is over the terrain.
    """

    brushSelected = QtCore.Signal(str)
    optionsChanged = QtCore.Signal(int, float, float, float)
    walkabilityChanged = QtCore.Signal(bool)
    topViewRequested = QtCore.Signal()
    angledViewRequested = QtCore.Signal()
    frameTerrainRequested = QtCore.Signal()
    exitRequested = QtCore.Signal()

    _BRUSHES = (
        ("raise", "Raise"),
        ("lower", "Lower"),
        ("smooth", "Smooth"),
        ("flatten", "Flatten"),
        ("plateau", "Plateau"),
        ("ramp", "Ramp"),
        ("terrace", "Terrace"),
        ("erode", "Erode"),
        ("noise", "Noise"),
        ("pinch", "Pinch"),
        ("erase", "Erase / Reset"),
    )

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("mapStudioTerrainSculptShelf")
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 5, 6, 5)
        root.setSpacing(5)

        tools = QtWidgets.QHBoxLayout()
        tools.setContentsMargins(0, 0, 0, 0)
        tools.setSpacing(4)
        mode_label = QtWidgets.QLabel("TERRAIN SCULPT", self)
        mode_label.setObjectName("mapStudioTerrainSculptModeLabel")
        mode_label.setToolTip("A KOTOR-safe static heightfield editing mode. Geometry and WOK are baked on export.")
        tools.addWidget(mode_label)

        self.brush_group = QtWidgets.QButtonGroup(self)
        self.brush_group.setExclusive(True)
        self.brush_buttons: dict[str, QtWidgets.QToolButton] = {}
        for key, label in self._BRUSHES[:4]:
            button = QtWidgets.QToolButton(self)
            button.setObjectName(f"mapStudioTerrainBrush{key.title()}Button")
            button.setText(label)
            button.setCheckable(True)
            button.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
            button.setToolTip(self._brush_tooltip(key))
            button.clicked.connect(lambda _checked=False, brush=key: self._choose_brush(brush))
            self.brush_group.addButton(button)
            self.brush_buttons[key] = button
            tools.addWidget(button)

        self.more_brushes = QtWidgets.QComboBox(self)
        self.more_brushes.setObjectName("mapStudioTerrainMoreBrushesComboBox")
        self.more_brushes.setMinimumContentsLength(9)
        self.more_brushes.addItem("More brushes…", "")
        for key, label in self._BRUSHES[4:]:
            self.more_brushes.addItem(label, key)
            index = self.more_brushes.count() - 1
            self.more_brushes.setItemData(index, self._brush_tooltip(key), QtCore.Qt.ToolTipRole)
        self.more_brushes.currentIndexChanged.connect(self._choose_more_brush)
        tools.addWidget(self.more_brushes)
        tools.addStretch(1)

        self.top_view_button = QtWidgets.QToolButton(self)
        self.top_view_button.setObjectName("mapStudioTerrainTopViewButton")
        self.top_view_button.setText("Top")
        self.top_view_button.setToolTip("Look straight down for paths, shorelines, and broad terrain shapes.")
        self.top_view_button.clicked.connect(self.topViewRequested.emit)
        tools.addWidget(self.top_view_button)
        self.angled_view_button = QtWidgets.QToolButton(self)
        self.angled_view_button.setObjectName("mapStudioTerrainAngledViewButton")
        self.angled_view_button.setText("Angled")
        self.angled_view_button.setToolTip("Use a readable three-quarter sculpting view.")
        self.angled_view_button.clicked.connect(self.angledViewRequested.emit)
        tools.addWidget(self.angled_view_button)
        self.frame_button = QtWidgets.QToolButton(self)
        self.frame_button.setObjectName("mapStudioTerrainFrameButton")
        self.frame_button.setText("Frame")
        self.frame_button.setToolTip("Frame all authored terrain in the viewport.")
        self.frame_button.clicked.connect(self.frameTerrainRequested.emit)
        tools.addWidget(self.frame_button)
        self.exit_button = QtWidgets.QToolButton(self)
        self.exit_button.setObjectName("mapStudioTerrainExitSculptButton")
        self.exit_button.setText("Exit Sculpt")
        self.exit_button.setToolTip("Return to normal object selection and transform controls.")
        self.exit_button.clicked.connect(self.exitRequested.emit)
        tools.addWidget(self.exit_button)
        root.addLayout(tools)

        settings = QtWidgets.QHBoxLayout()
        settings.setContentsMargins(0, 0, 0, 0)
        settings.setSpacing(5)
        self.radius_spin = QtWidgets.QSpinBox(self)
        self.radius_spin.setObjectName("mapStudioTerrainShelfRadiusSpinBox")
        self.radius_spin.setRange(0, 64)
        self.radius_spin.setValue(3)
        self.radius_spin.setSuffix(" cells")
        self.radius_spin.setToolTip("Brush radius. Hold Shift and scroll over the viewport to resize it.")
        self.hardness_spin = self._unit_spin("mapStudioTerrainShelfHardnessSpinBox", 0.5)
        self.hardness_spin.setToolTip("Hard center versus soft falloff. The inner cursor ring shows this value.")
        self.strength_spin = self._unit_spin("mapStudioTerrainShelfStrengthSpinBox", 0.5)
        self.strength_spin.setToolTip("How strongly smooth, flatten, and shaping brushes affect each stroke.")
        self.delta_spin = QtWidgets.QDoubleSpinBox(self)
        self.delta_spin.setObjectName("mapStudioTerrainShelfHeightChangeSpinBox")
        self.delta_spin.setRange(0.01, 100.0)
        self.delta_spin.setDecimals(2)
        self.delta_spin.setSingleStep(0.05)
        self.delta_spin.setValue(0.10)
        self.delta_spin.setSuffix(" m")
        self.delta_spin.setToolTip("Height change per raise/lower stamp in KOTOR world metres.")
        for label, widget in (
            ("Size", self.radius_spin),
            ("Falloff", self.hardness_spin),
            ("Strength", self.strength_spin),
            ("Height", self.delta_spin),
        ):
            settings.addWidget(QtWidgets.QLabel(label, self))
            settings.addWidget(widget)

        self.walkability_box = QtWidgets.QCheckBox("Slope / WOK overlay", self)
        self.walkability_box.setObjectName("mapStudioTerrainSlopeOverlayCheckBox")
        self.walkability_box.setChecked(False)
        self.walkability_box.setToolTip(
            "Show walkable and blocked WOK triangles. Leave off while shaping for a clean surface; enable before export."
        )
        settings.addWidget(self.walkability_box)
        settings.addStretch(1)
        self.gesture_hint = QtWidgets.QLabel(
            "LMB sculpt  ·  Shift+LMB lower  ·  RMB orbit  ·  Alt+MMB pan  ·  Shift+wheel resize  ·  Alt+RMB size/falloff",
            self,
        )
        self.gesture_hint.setObjectName("mapStudioTerrainGestureHintLabel")
        settings.addWidget(self.gesture_hint)
        root.addLayout(settings)

        self.radius_spin.valueChanged.connect(self._emit_options)
        self.hardness_spin.valueChanged.connect(self._emit_options)
        self.strength_spin.valueChanged.connect(self._emit_options)
        self.delta_spin.valueChanged.connect(self._emit_options)
        self.walkability_box.toggled.connect(self.walkabilityChanged.emit)
        self.set_brush("raise")

    @staticmethod
    def _unit_spin(object_name: str, value: float) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setObjectName(object_name)
        spin.setRange(0.0, 1.0)
        spin.setDecimals(2)
        spin.setSingleStep(0.05)
        spin.setValue(value)
        return spin

    @staticmethod
    def _brush_tooltip(key: str) -> str:
        return {
            "raise": "Raise terrain. Hold Shift during a Raise stroke to lower temporarily.",
            "lower": "Lower terrain while preserving the static heightfield boundary.",
            "smooth": "Relax spikes and harsh slopes for a safer KOTOR walkmesh.",
            "flatten": "Blend toward the exact target height from Terrain Building.",
            "plateau": "Pull the area toward the sampled center height for combat pads and landings.",
            "ramp": "Draw a directional grade between the beginning and end of one stroke.",
            "terrace": "Quantize the surface into deterministic stepped height bands.",
            "erode": "Apply a lightweight, baked erosion-style relaxation pass.",
            "noise": "Add deterministic static height variation; validate slopes after painting.",
            "pinch": "Tighten a ridge or channel toward the brush-center height.",
            "erase": "Blend locally back toward the base height without clearing the terrain.",
        }.get(key, "Select this terrain sculpt brush.")

    def _choose_brush(self, brush: str) -> None:
        self.set_brush(brush)
        self.brushSelected.emit(str(brush))

    def _choose_more_brush(self, index: int) -> None:
        brush = str(self.more_brushes.itemData(index) or "")
        if not brush:
            return
        self.set_brush(brush)
        self.brushSelected.emit(brush)

    def _emit_options(self, _value: object = None) -> None:
        self.optionsChanged.emit(
            int(self.radius_spin.value()),
            float(self.hardness_spin.value()),
            float(self.strength_spin.value()),
            float(self.delta_spin.value()),
        )

    def set_brush(self, brush: str) -> None:
        wanted = str(brush or "raise").strip().lower()
        self.brush_group.setExclusive(False)
        for key, button in self.brush_buttons.items():
            blocked = button.blockSignals(True)
            button.setChecked(key == wanted)
            button.blockSignals(blocked)
        self.brush_group.setExclusive(True)
        advanced_index = self.more_brushes.findData(wanted)
        blocked = self.more_brushes.blockSignals(True)
        self.more_brushes.setCurrentIndex(advanced_index if advanced_index >= 0 else 0)
        self.more_brushes.blockSignals(blocked)
        label = next((label for key, label in self._BRUSHES if key == wanted), wanted.title())
        self.setProperty("activeTerrainBrush", wanted)
        self.setToolTip(f"Terrain Sculpt — {label}")

    def set_options(self, *, radius: int, hardness: float, strength: float, delta: float) -> None:
        for widget, value in (
            (self.radius_spin, int(radius)),
            (self.hardness_spin, float(hardness)),
            (self.strength_spin, float(strength)),
            (self.delta_spin, float(delta)),
        ):
            blocked = widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(blocked)


__all__ = ["TerrainSculptShelf"]
