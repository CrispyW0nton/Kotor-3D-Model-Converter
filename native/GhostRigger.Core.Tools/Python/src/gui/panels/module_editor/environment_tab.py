"""Map Studio Environment presentation for lighting, weather, fog, and lightmaps."""

from __future__ import annotations

from typing import Any

from PySide6 import QtCore, QtWidgets

from src.core.modules.authored_skybox import (
    available_kotor_skybox_presets,
    kotor_skybox_preset,
)


class MapStudioEnvironmentTab(QtWidgets.QWidget):
    """Presentation-only Environment tab; engine policy stays in core modules."""

    worldSettingsRequested = QtCore.Signal(dict)
    lightmapApplyRequested = QtCore.Signal(dict)
    skyboxCreateRequested = QtCore.Signal(dict)
    skyPanoramaRequested = QtCore.Signal(dict)
    skyTrafficCreateRequested = QtCore.Signal(dict)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("mapStudioEnvironmentTab")
        self._loading = False
        self._last_profile = "standard"
        self._standard_values: dict[str, Any] = {}
        self._lightmap_rows: tuple[dict[str, Any], ...] = ()

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(8)
        self._root_layout = root

        self.world_group = QtWidgets.QGroupBox("Lighting, Weather and Fog (ARE)", self)
        self.world_group.setObjectName("mapStudioEnvironmentWorldGroup")
        world_layout = QtWidgets.QVBoxLayout(self.world_group)
        world_form = QtWidgets.QFormLayout()
        world_layout.addLayout(world_form)

        self.profile_combo = QtWidgets.QComboBox(self.world_group)
        self.profile_combo.setObjectName("mapStudioWorldLightingProfileComboBox")
        self.profile_combo.addItem("Standard / Match Module", "standard")
        self.profile_combo.addItem("Fullbright Graybox", "fullbright")
        self.profile_combo.addItem("Custom", "custom")
        self.profile_combo.setToolTip(
            "Standard preserves loaded/authored ARE values. Fullbright is a fixed white, no-shadow, no-fog graybox overlay."
        )
        world_form.addRow("Profile", self.profile_combo)

        self.profile_hint = QtWidgets.QLabel(self.world_group)
        self.profile_hint.setObjectName("mapStudioWorldLightingProfileHintLabel")
        self.profile_hint.setWordWrap(True)
        world_layout.addWidget(self.profile_hint)

        self.sun_ambient_widget, self.sun_ambient_spins = self._rgb_editor(
            "mapStudioWorldSunAmbient", self.world_group
        )
        world_form.addRow("Sun ambient RGB", self.sun_ambient_widget)
        self.sun_diffuse_widget, self.sun_diffuse_spins = self._rgb_editor(
            "mapStudioWorldSunDiffuse", self.world_group
        )
        world_form.addRow("Sun diffuse RGB", self.sun_diffuse_widget)
        self.dynamic_ambient_widget, self.dynamic_ambient_spins = self._rgb_editor(
            "mapStudioWorldDynamicAmbient", self.world_group
        )
        world_form.addRow("Dynamic ambient RGB", self.dynamic_ambient_widget)

        self.shadow_opacity_spin = QtWidgets.QSpinBox(self.world_group)
        self.shadow_opacity_spin.setObjectName("mapStudioWorldShadowOpacitySpinBox")
        self.shadow_opacity_spin.setRange(0, 255)
        self.shadow_opacity_spin.setToolTip("KOTOR ARE ShadowOpacity byte (0-255).")
        world_form.addRow("Shadow opacity", self.shadow_opacity_spin)

        self.sun_shadows_check = QtWidgets.QCheckBox("Enable KOTOR sun shadows", self.world_group)
        self.sun_shadows_check.setObjectName("mapStudioWorldSunShadowsCheckBox")
        world_form.addRow("Sun shadows", self.sun_shadows_check)

        self.fog_enabled_check = QtWidgets.QCheckBox("Enable distance fog", self.world_group)
        self.fog_enabled_check.setObjectName("mapStudioWorldFogEnabledCheckBox")
        world_form.addRow("Fog", self.fog_enabled_check)

        self.fog_color_widget, self.fog_color_spins = self._rgb_editor(
            "mapStudioWorldFogColor", self.world_group
        )
        world_form.addRow("Fog color RGB", self.fog_color_widget)

        self.fog_near_spin = self._distance_spin("mapStudioWorldFogNearSpinBox", self.world_group)
        world_form.addRow("Fog near", self.fog_near_spin)
        self.fog_far_spin = self._distance_spin("mapStudioWorldFogFarSpinBox", self.world_group)
        world_form.addRow("Fog far", self.fog_far_spin)

        self.world_apply_button = QtWidgets.QPushButton("Apply World Settings", self.world_group)
        self.world_apply_button.setObjectName("mapStudioWorldSettingsApplyButton")
        self.world_apply_button.setToolTip(
            "Persist these values in KMAP, refresh the approximate realtime lighting preview, and mark ARE/module "
            "export and game proof stale."
        )
        world_layout.addWidget(self.world_apply_button)

        self.world_status_label = QtWidgets.QLabel(self.world_group)
        self.world_status_label.setObjectName("mapStudioWorldSettingsStatusLabel")
        self.world_status_label.setWordWrap(True)
        world_layout.addWidget(self.world_status_label)
        root.addWidget(self.world_group)

        self.lightmap_group = QtWidgets.QGroupBox("Lights & Lightmaps", self)
        self.lightmap_group.setObjectName("mapStudioEnvironmentLightmapsGroup")
        lightmap_layout = QtWidgets.QVBoxLayout(self.lightmap_group)
        lightmap_form = QtWidgets.QFormLayout()
        lightmap_layout.addLayout(lightmap_form)
        self.lightmap_room_combo = QtWidgets.QComboBox(self.lightmap_group)
        self.lightmap_room_combo.setObjectName("mapStudioLightmapRoomComboBox")
        lightmap_form.addRow("Room", self.lightmap_room_combo)
        self.lightmap_surface_combo = QtWidgets.QComboBox(self.lightmap_group)
        self.lightmap_surface_combo.setObjectName("mapStudioLightmapSurfaceComboBox")
        lightmap_form.addRow("Surface", self.lightmap_surface_combo)
        self.lightmap_resref_edit = QtWidgets.QLineEdit(self.lightmap_group)
        self.lightmap_resref_edit.setObjectName("mapStudioLightmapResrefLineEdit")
        self.lightmap_resref_edit.setMaxLength(16)
        self.lightmap_resref_edit.setToolTip("KOTOR lightmap texture resref; the applied resource is a vanilla-shaped TPC.")
        lightmap_form.addRow("Lightmap resref", self.lightmap_resref_edit)
        self.lightmap_resolution_combo = QtWidgets.QComboBox(self.lightmap_group)
        self.lightmap_resolution_combo.setObjectName("mapStudioLightmapResolutionComboBox")
        for resolution in (64, 128, 256, 512, 1024):
            self.lightmap_resolution_combo.addItem(f"{resolution} x {resolution}", resolution)
        lightmap_form.addRow("Resolution", self.lightmap_resolution_combo)
        self.lightmap_world_ambient_check = QtWidgets.QCheckBox("Bake ARE world ambient", self.lightmap_group)
        self.lightmap_world_ambient_check.setObjectName("mapStudioLightmapWorldAmbientCheckBox")
        self.lightmap_world_ambient_check.setChecked(True)
        lightmap_form.addRow("World lighting", self.lightmap_world_ambient_check)
        self.lightmap_shadows_check = QtWidgets.QCheckBox("Use shadow-casting room lights", self.lightmap_group)
        self.lightmap_shadows_check.setObjectName("mapStudioLightmapShadowsCheckBox")
        self.lightmap_shadows_check.setChecked(True)
        lightmap_form.addRow("Shadows", self.lightmap_shadows_check)
        self.lightmap_apply_button = QtWidgets.QPushButton("Bake & Apply Selected Surface", self.lightmap_group)
        self.lightmap_apply_button.setObjectName("mapStudioApplySurfaceLightmapButton")
        self.lightmap_apply_button.setToolTip(
            "Generate/remap UV2, bake enabled room lights, assign MDL slot 2, and persist a KOTOR TPC beside the saved KMAP."
        )
        lightmap_layout.addWidget(self.lightmap_apply_button)
        self.lightmap_status_label = QtWidgets.QLabel(self.lightmap_group)
        self.lightmap_status_label.setObjectName("mapStudioLightmapStatusLabel")
        self.lightmap_status_label.setWordWrap(True)
        lightmap_layout.addWidget(self.lightmap_status_label)
        root.addWidget(self.lightmap_group)
        self.sky_group = QtWidgets.QGroupBox("KOTOR Sky Dome", self)
        self.sky_group.setObjectName("mapStudioEnvironmentSkyGroup")
        sky_layout = QtWidgets.QVBoxLayout(self.sky_group)
        sky_form = QtWidgets.QFormLayout()
        sky_layout.addLayout(sky_form)
        self.sky_preset_combo = QtWidgets.QComboBox(self.sky_group)
        self.sky_preset_combo.setObjectName("mapStudioSkyboxPresetComboBox")
        self.sky_preset_combo.setAccessibleName("Vanilla sky style")
        self.sky_preset_combo.setToolTip(
            "Choose a measured sky texture set from an installed KOTOR module, "
            "or keep Custom to enter five texture ResRefs manually."
        )
        sky_form.addRow("Vanilla sky", self.sky_preset_combo)
        self.sky_room_resref_edit = QtWidgets.QLineEdit(self.sky_group)
        self.sky_room_resref_edit.setObjectName("mapStudioSkyRoomResrefLineEdit")
        self.sky_room_resref_edit.setMaxLength(16)
        self.sky_room_resref_edit.setToolTip("KOTOR room-model resref (16 characters maximum).")
        sky_form.addRow("Sky room", self.sky_room_resref_edit)
        self.sky_texture_edits: dict[str, QtWidgets.QLineEdit] = {}
        for face in ("north", "east", "south", "west", "top"):
            edit = QtWidgets.QLineEdit(self.sky_group)
            edit.setObjectName(f"mapStudioSky{face.title()}TextureLineEdit")
            edit.setMaxLength(16)
            edit.setToolTip(f"Imported KOTOR texture resref for the {face} inward-facing dome sector.")
            self.sky_texture_edits[face] = edit
            sky_form.addRow(f"{face.title()} texture", edit)
        self.sky_half_extent_spin = self._distance_spin("mapStudioSkyHalfExtentSpinBox", self.sky_group)
        self.sky_half_extent_spin.setRange(1.0, 100_000.0)
        self.sky_half_extent_spin.setValue(500.0)
        sky_form.addRow("Half extent", self.sky_half_extent_spin)
        self.sky_bottom_z_spin = self._signed_distance_spin("mapStudioSkyBottomZSpinBox", self.sky_group)
        self.sky_bottom_z_spin.setValue(-500.0)
        sky_form.addRow("Bottom Z", self.sky_bottom_z_spin)
        self.sky_top_z_spin = self._signed_distance_spin("mapStudioSkyTopZSpinBox", self.sky_group)
        self.sky_top_z_spin.setValue(500.0)
        sky_form.addRow("Top Z", self.sky_top_z_spin)
        self.sky_create_button = QtWidgets.QPushButton("Create KOTOR Sky Dome", self.sky_group)
        self.sky_create_button.setObjectName("mapStudioCreateFiveFaceSkyboxButton")
        self.sky_create_button.setToolTip(
            "Create a curved, inward-facing visual-only sky room from four cardinal textures plus a top texture. "
            "The room exports with an exact empty WOK."
        )
        sky_layout.addWidget(self.sky_create_button)
        self.sky_panorama_button = QtWidgets.QPushButton("Create from Panorama / HDR...", self.sky_group)
        self.sky_panorama_button.setObjectName("mapStudioSkyPanoramaConversionButton")
        self.sky_panorama_button.setToolTip(
            "Project an equirectangular panorama into five KOTOR-oriented dome sectors. HDR/EXR input is tone-mapped "
            "offline into engine-compatible 8-bit TGA textures."
        )
        sky_layout.addWidget(self.sky_panorama_button)
        self.sky_status_label = QtWidgets.QLabel(
            "Loaded module sky/backdrop surfaces render with their game textures by default and remain non-selectable. "
            "Create a curved sky room from existing textures, or convert a panorama/HDR source into five project "
            "textures. KOTOR does not consume modern HDR environment maps directly, so HDR light values are "
            "tone-mapped offline before export.",
            self.sky_group,
        )
        self.sky_status_label.setObjectName("mapStudioEnvironmentSkyStatusLabel")
        self.sky_status_label.setWordWrap(True)
        sky_layout.addWidget(self.sky_status_label)
        root.addWidget(self.sky_group)
        self.sky_traffic_group = QtWidgets.QGroupBox("Sky Traffic", self)
        self.sky_traffic_group.setObjectName("mapStudioEnvironmentSkyTrafficGroup")
        traffic_layout = QtWidgets.QVBoxLayout(self.sky_traffic_group)
        traffic_form = QtWidgets.QFormLayout()
        traffic_layout.addLayout(traffic_form)
        self.sky_traffic_name_edit = QtWidgets.QLineEdit("Sky Traffic", self.sky_traffic_group)
        self.sky_traffic_name_edit.setObjectName("mapStudioSkyTrafficNameLineEdit")
        traffic_form.addRow("Name", self.sky_traffic_name_edit)
        self.sky_traffic_room_combo = QtWidgets.QComboBox(self.sky_traffic_group)
        self.sky_traffic_room_combo.setObjectName("mapStudioSkyTrafficRoomComboBox")
        traffic_form.addRow("Host room", self.sky_traffic_room_combo)
        self.sky_traffic_model_edit = QtWidgets.QLineEdit(self.sky_traffic_group)
        self.sky_traffic_model_edit.setObjectName("mapStudioSkyTrafficModelResrefLineEdit")
        self.sky_traffic_model_edit.setMaxLength(16)
        self.sky_traffic_model_edit.setToolTip(
            "Direct MDL model resref, such as C_Brith. This is previewed as an actor but compiles into the host room animation."
        )
        traffic_form.addRow("Flying model", self.sky_traffic_model_edit)
        self.sky_traffic_slot_combo = QtWidgets.QComboBox(self.sky_traffic_group)
        self.sky_traffic_slot_combo.setObjectName("mapStudioSkyTrafficAnimationSlotComboBox")
        for slot in ("animloop1", "animloop2", "animloop3"):
            self.sky_traffic_slot_combo.addItem(slot, slot)
        traffic_form.addRow("Room loop", self.sky_traffic_slot_combo)
        self.sky_traffic_timing_combo = QtWidgets.QComboBox(self.sky_traffic_group)
        self.sky_traffic_timing_combo.setObjectName("mapStudioSkyTrafficTimingModeComboBox")
        self.sky_traffic_timing_combo.addItem("Loop duration", "duration")
        self.sky_traffic_timing_combo.addItem("Travel speed", "speed")
        traffic_form.addRow("Timing", self.sky_traffic_timing_combo)
        self.sky_traffic_duration_spin = QtWidgets.QDoubleSpinBox(self.sky_traffic_group)
        self.sky_traffic_duration_spin.setObjectName("mapStudioSkyTrafficDurationSpinBox")
        self.sky_traffic_duration_spin.setRange(0.1, 3_600.0)
        self.sky_traffic_duration_spin.setDecimals(3)
        self.sky_traffic_duration_spin.setValue(30.0)
        self.sky_traffic_duration_spin.setSuffix(" s")
        traffic_form.addRow("Loop duration", self.sky_traffic_duration_spin)
        self.sky_traffic_speed_spin = QtWidgets.QDoubleSpinBox(self.sky_traffic_group)
        self.sky_traffic_speed_spin.setObjectName("mapStudioSkyTrafficSpeedSpinBox")
        self.sky_traffic_speed_spin.setRange(0.01, 100_000.0)
        self.sky_traffic_speed_spin.setDecimals(3)
        self.sky_traffic_speed_spin.setValue(10.0)
        self.sky_traffic_speed_spin.setSuffix(" units/s")
        traffic_form.addRow("Travel speed", self.sky_traffic_speed_spin)
        self.sky_traffic_start_widget, self.sky_traffic_start_spins = self._vec3_editor(
            "mapStudioSkyTrafficStart", self.sky_traffic_group
        )
        traffic_form.addRow("Start XYZ", self.sky_traffic_start_widget)
        self.sky_traffic_end_widget, self.sky_traffic_end_spins = self._vec3_editor(
            "mapStudioSkyTrafficEnd", self.sky_traffic_group
        )
        self.sky_traffic_end_spins[0].setValue(50.0)
        traffic_form.addRow("End XYZ", self.sky_traffic_end_widget)
        self.sky_traffic_closed_check = QtWidgets.QCheckBox("Close path back to start", self.sky_traffic_group)
        self.sky_traffic_closed_check.setObjectName("mapStudioSkyTrafficClosedPathCheckBox")
        traffic_form.addRow("Path", self.sky_traffic_closed_check)
        self.sky_traffic_create_button = QtWidgets.QPushButton("Create Flight Path Actor", self.sky_traffic_group)
        self.sky_traffic_create_button.setObjectName("mapStudioCreateSkyTrafficButton")
        self.sky_traffic_create_button.setToolTip(
            "Place the actual source model at the path start and draw cyan direction arrows. KMAP targets room-MDL animloop export, never GIT."
        )
        traffic_layout.addWidget(self.sky_traffic_create_button)
        self.sky_traffic_status_label = QtWidgets.QLabel(self.sky_traffic_group)
        self.sky_traffic_status_label.setObjectName("mapStudioEnvironmentSkyTrafficStatusLabel")
        self.sky_traffic_status_label.setWordWrap(True)
        traffic_layout.addWidget(self.sky_traffic_status_label)
        root.addWidget(self.sky_traffic_group)
        root.addStretch(1)

        self._fullbright_overridden_widgets = (
            *self.sun_ambient_spins,
            *self.sun_diffuse_spins,
            *self.dynamic_ambient_spins,
            self.shadow_opacity_spin,
            self.sun_shadows_check,
            self.fog_enabled_check,
            *self.fog_color_spins,
            self.fog_near_spin,
            self.fog_far_spin,
        )
        self.profile_combo.currentIndexChanged.connect(self._handle_profile_changed)
        self.world_apply_button.clicked.connect(self._emit_world_settings)
        self.lightmap_apply_button.clicked.connect(self._emit_lightmap_apply)
        self.lightmap_room_combo.currentIndexChanged.connect(self._refresh_lightmap_surfaces)
        self.lightmap_surface_combo.currentIndexChanged.connect(self._refresh_lightmap_default_resref)
        self.sky_create_button.clicked.connect(self._emit_skybox_create)
        self.sky_panorama_button.clicked.connect(self._emit_sky_panorama)
        self.sky_preset_combo.currentIndexChanged.connect(self._apply_skybox_preset)
        self.sky_traffic_create_button.clicked.connect(self._emit_sky_traffic_create)
        self.sky_traffic_timing_combo.currentIndexChanged.connect(self._sync_sky_traffic_timing_controls)
        self._sync_sky_traffic_timing_controls()
        self._update_profile_presentation()
        self.set_world_settings({"available": False})

    def adopt_room_lighting_tools(self, room_lighting_group: QtWidgets.QWidget) -> None:
        """Place Builder-owned room-light authoring alongside Environment lighting controls."""

        room_lighting_group.setParent(self)
        self._root_layout.insertWidget(self._root_layout.count() - 1, room_lighting_group)
        room_lighting_group.show()

    @staticmethod
    def _rgb_editor(prefix: str, parent: QtWidgets.QWidget) -> tuple[QtWidgets.QWidget, tuple[QtWidgets.QSpinBox, ...]]:
        widget = QtWidgets.QWidget(parent)
        widget.setObjectName(f"{prefix}Widget")
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        spins = []
        for channel, suffix in (("R", "Red"), ("G", "Green"), ("B", "Blue")):
            label = QtWidgets.QLabel(channel, widget)
            label.setObjectName(f"{prefix}{suffix}Label")
            spin = QtWidgets.QSpinBox(widget)
            spin.setObjectName(f"{prefix}{suffix}SpinBox")
            spin.setRange(0, 255)
            layout.addWidget(label)
            layout.addWidget(spin, 1)
            spins.append(spin)
        return widget, tuple(spins)

    @staticmethod
    def _vec3_editor(prefix: str, parent: QtWidgets.QWidget) -> tuple[QtWidgets.QWidget, tuple[QtWidgets.QDoubleSpinBox, ...]]:
        widget = QtWidgets.QWidget(parent)
        widget.setObjectName(f"{prefix}Widget")
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        spins = []
        for channel in ("X", "Y", "Z"):
            label = QtWidgets.QLabel(channel, widget)
            spin = QtWidgets.QDoubleSpinBox(widget)
            spin.setObjectName(f"{prefix}{channel}SpinBox")
            spin.setRange(-1_000_000.0, 1_000_000.0)
            spin.setDecimals(2)
            layout.addWidget(label)
            layout.addWidget(spin, 1)
            spins.append(spin)
        return widget, tuple(spins)

    @staticmethod
    def _distance_spin(object_name: str, parent: QtWidgets.QWidget) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox(parent)
        spin.setObjectName(object_name)
        spin.setRange(0.0, 1_000_000.0)
        spin.setDecimals(2)
        spin.setSingleStep(1.0)
        spin.setSuffix(" m")
        return spin

    @staticmethod
    def _signed_distance_spin(object_name: str, parent: QtWidgets.QWidget) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox(parent)
        spin.setObjectName(object_name)
        spin.setRange(-1_000_000.0, 1_000_000.0)
        spin.setDecimals(2)
        spin.setSingleStep(10.0)
        spin.setSuffix(" m")
        return spin

    @staticmethod
    def _add_status_group(
        root: QtWidgets.QVBoxLayout,
        *,
        title: str,
        object_name: str,
        text: str,
    ) -> None:
        group = QtWidgets.QGroupBox(title)
        group.setObjectName(object_name)
        layout = QtWidgets.QVBoxLayout(group)
        label = QtWidgets.QLabel(text, group)
        label.setObjectName(f"{object_name}Label")
        label.setWordWrap(True)
        layout.addWidget(label)
        root.addWidget(group)

    @staticmethod
    def _rgb(spins: tuple[QtWidgets.QSpinBox, ...]) -> tuple[int, int, int]:
        return tuple(int(spin.value()) for spin in spins)  # type: ignore[return-value]

    @staticmethod
    def _set_rgb(spins: tuple[QtWidgets.QSpinBox, ...], value: Any) -> None:
        channels = tuple(value or ())
        if len(channels) < 3:
            return
        for spin, channel in zip(spins, channels):
            spin.setValue(max(0, min(255, int(channel))))

    def world_settings(self) -> dict[str, Any]:
        """Return presentation values for the headless controller update."""

        return {
            "profile": str(self.profile_combo.currentData() or "standard"),
            "sun_ambient": self._rgb(self.sun_ambient_spins),
            "sun_diffuse": self._rgb(self.sun_diffuse_spins),
            "dynamic_ambient": self._rgb(self.dynamic_ambient_spins),
            "shadow_opacity": int(self.shadow_opacity_spin.value()),
            "sun_shadows": bool(self.sun_shadows_check.isChecked()),
            "fog_enabled": bool(self.fog_enabled_check.isChecked()),
            "fog_color": self._rgb(self.fog_color_spins),
            "fog_near": float(self.fog_near_spin.value()),
            "fog_far": float(self.fog_far_spin.value()),
        }

    def skybox_settings(self) -> dict[str, Any]:
        """Return the five-face recipe requested from the headless controller."""

        preset_id = str(self.sky_preset_combo.currentData() or "")
        preset = kotor_skybox_preset(preset_id)
        return {
            "room_resref": self.sky_room_resref_edit.text().strip(),
            "north_texture": self.sky_texture_edits["north"].text().strip(),
            "east_texture": self.sky_texture_edits["east"].text().strip(),
            "south_texture": self.sky_texture_edits["south"].text().strip(),
            "west_texture": self.sky_texture_edits["west"].text().strip(),
            "top_texture": self.sky_texture_edits["top"].text().strip(),
            "half_extent": float(self.sky_half_extent_spin.value()),
            "bottom_z": float(self.sky_bottom_z_spin.value()),
            "top_z": float(self.sky_top_z_spin.value()),
            "visible_rooms": tuple(getattr(self, "_sky_visible_rooms", ())),
            "authoring_metadata": (
                {
                    "skybox_preset_id": preset.preset_id,
                    "skybox_source_game": preset.game,
                    "skybox_source_module": preset.source_module,
                    "skybox_source_room": preset.source_room,
                    "skybox_source": "measured_vanilla_module_textures",
                }
                if preset is not None
                else {}
            ),
        }

    def lightmap_settings(self) -> dict[str, Any]:
        row = self.lightmap_surface_combo.currentData()
        surface = dict(row) if isinstance(row, dict) else {}
        return {
            "room_resref": str(surface.get("room_resref") or self.lightmap_room_combo.currentData() or ""),
            "surface_role_or_index": str(surface.get("surface_role") or ""),
            "lightmap_resref": self.lightmap_resref_edit.text().strip(),
            "resolution": int(self.lightmap_resolution_combo.currentData() or 64),
            "include_world_ambient": bool(self.lightmap_world_ambient_check.isChecked()),
            "use_shadows": bool(self.lightmap_shadows_check.isChecked()),
        }

    def set_lightmap_context(
        self,
        rows: Any = (),
        *,
        project_saved: bool = False,
        light_count: int = 0,
    ) -> None:
        self._lightmap_rows = tuple(dict(row) for row in tuple(rows or ()) if isinstance(row, dict))
        selected_room = str(self.lightmap_room_combo.currentData() or "")
        rooms = tuple(dict.fromkeys(str(row.get("room_resref") or "") for row in self._lightmap_rows if row.get("room_resref")))
        self.lightmap_room_combo.blockSignals(True)
        try:
            self.lightmap_room_combo.clear()
            for room in rooms:
                self.lightmap_room_combo.addItem(room, room)
            index = self.lightmap_room_combo.findData(selected_room)
            self.lightmap_room_combo.setCurrentIndex(index if index >= 0 else (0 if rooms else -1))
        finally:
            self.lightmap_room_combo.blockSignals(False)
        self._refresh_lightmap_surfaces()
        available = bool(self._lightmap_rows) and bool(project_saved)
        self.lightmap_group.setEnabled(bool(self._lightmap_rows))
        self.lightmap_apply_button.setEnabled(available)
        if not self._lightmap_rows:
            message = "Convert or create an imported-mesh room before baking lightmaps."
        elif not project_saved:
            message = "Save the KMAP first; generated TPC lightmaps live beside the project as reference-heavy sidecars."
        else:
            applied = sum(1 for row in self._lightmap_rows if str(row.get("bake_status")) == "headless_bake_complete")
            message = (
                f"{int(light_count)} room light(s), {len(self._lightmap_rows)} surface(s), {applied} applied bake(s). "
                "TPC output matches the vanilla 001ebo1 binary structure; a manual KOTOR warp is still required."
            )
        self.lightmap_status_label.setText(message)

    def set_lightmap_status(self, message: str) -> None:
        self.lightmap_status_label.setText(str(message or ""))

    def _refresh_lightmap_surfaces(self, _index: int = -1) -> None:
        room = str(self.lightmap_room_combo.currentData() or "")
        previous_role = ""
        previous = self.lightmap_surface_combo.currentData()
        if isinstance(previous, dict):
            previous_role = str(previous.get("surface_role") or "")
        self.lightmap_surface_combo.blockSignals(True)
        try:
            self.lightmap_surface_combo.clear()
            for row in self._lightmap_rows:
                if str(row.get("room_resref") or "") != room:
                    continue
                status = str(row.get("bake_status") or "not_baked").replace("_", " ")
                label = f"{row.get('surface_name') or row.get('surface_role')} ({row.get('face_count', 0)} faces; {status})"
                self.lightmap_surface_combo.addItem(label, dict(row))
            selected = -1
            for index in range(self.lightmap_surface_combo.count()):
                data = self.lightmap_surface_combo.itemData(index)
                if isinstance(data, dict) and str(data.get("surface_role") or "") == previous_role:
                    selected = index
                    break
            self.lightmap_surface_combo.setCurrentIndex(selected if selected >= 0 else (0 if self.lightmap_surface_combo.count() else -1))
        finally:
            self.lightmap_surface_combo.blockSignals(False)
        self._refresh_lightmap_default_resref()

    def _refresh_lightmap_default_resref(self, _index: int = -1) -> None:
        row = self.lightmap_surface_combo.currentData()
        if not isinstance(row, dict):
            self.lightmap_resref_edit.clear()
            return
        existing = str(row.get("lightmap_resref") or "").strip().lower()
        room = str(row.get("room_resref") or "room").strip().lower()
        surface_index = int(row.get("surface_index") or 0)
        self.lightmap_resref_edit.setText(existing or f"{room[:11]}_lm{surface_index}"[:16])

    def sky_traffic_settings(self) -> dict[str, Any]:
        timing_mode = str(self.sky_traffic_timing_combo.currentData() or "duration")
        return {
            "name": self.sky_traffic_name_edit.text().strip() or "Sky Traffic",
            "room_resref": str(self.sky_traffic_room_combo.currentData() or ""),
            "model_resref": self.sky_traffic_model_edit.text().strip(),
            "animation_name": str(self.sky_traffic_slot_combo.currentData() or "animloop1"),
            "duration_seconds": float(self.sky_traffic_duration_spin.value()) if timing_mode == "duration" else None,
            "speed_units_per_second": float(self.sky_traffic_speed_spin.value()) if timing_mode == "speed" else None,
            "start": tuple(float(spin.value()) for spin in self.sky_traffic_start_spins),
            "end": tuple(float(spin.value()) for spin in self.sky_traffic_end_spins),
            "facing_mode": "path_tangent",
            "closed_path": bool(self.sky_traffic_closed_check.isChecked()),
        }

    def _sync_sky_traffic_timing_controls(self, _index: int = -1) -> None:
        speed_mode = str(self.sky_traffic_timing_combo.currentData() or "duration") == "speed"
        self.sky_traffic_duration_spin.setEnabled(not speed_mode)
        self.sky_traffic_speed_spin.setEnabled(speed_mode)

    def set_skybox_context(self, *, module_root: str = "", game: str = "K1", room_resrefs: Any = ()) -> None:
        """Keep sky authoring defaults aligned with the current KMAP project."""

        root = str(module_root or "").strip().lower()
        rooms = tuple(str(value or "").strip().lower() for value in tuple(room_resrefs or ()) if str(value or "").strip())
        self._sky_visible_rooms = rooms
        selected_preset = str(self.sky_preset_combo.currentData() or "")
        self.sky_preset_combo.blockSignals(True)
        try:
            self.sky_preset_combo.clear()
            self.sky_preset_combo.addItem("Custom / Existing Textures", "")
            for preset in available_kotor_skybox_presets(game):
                self.sky_preset_combo.addItem(preset.label, preset.preset_id)
            selected_index = self.sky_preset_combo.findData(selected_preset)
            self.sky_preset_combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
        finally:
            self.sky_preset_combo.blockSignals(False)
        self.sky_group.setEnabled(bool(root))
        self.sky_panorama_button.setEnabled(bool(root and rooms))
        if root and not self.sky_room_resref_edit.text().strip():
            self.sky_room_resref_edit.setText(f"{root[:12]}_sky"[:16])
        if root and not any(edit.text().strip() for edit in self.sky_texture_edits.values()):
            prefix = f"{root[:10]}sk"
            for face, suffix in (("north", "n"), ("east", "e"), ("south", "s"), ("west", "w"), ("top", "t")):
                self.sky_texture_edits[face].setText(f"{prefix}_{suffix}"[:16])
        self.sky_group.setToolTip(
            f"Create a {str(game or 'K1').upper()} visual-only sky dome visible from {len(rooms)} authored room(s)."
        )

    def _apply_skybox_preset(self, _index: int = -1) -> None:
        """Fill the five explicit fields from one retail-derived recipe."""

        preset = kotor_skybox_preset(str(self.sky_preset_combo.currentData() or ""))
        if preset is None:
            return
        for face, texture in preset.textures.ordered_items():
            self.sky_texture_edits[face].setText(texture)
        self.sky_half_extent_spin.setValue(float(preset.half_extent))
        self.sky_bottom_z_spin.setValue(float(preset.bottom_z))
        self.sky_top_z_spin.setValue(float(preset.top_z))
        self.sky_status_label.setText(
            f"Ready: {preset.label}. These are the original texture ResRefs from "
            f"{preset.source_room.upper()} in {preset.source_module.upper()}; Ghost Studio "
            "builds a curved visual-only dome and leaves collision untouched."
        )

    def set_skybox_status(self, message: str) -> None:
        self.sky_status_label.setText(str(message or ""))

    def set_sky_traffic_context(self, *, room_resrefs: Any = (), traffic_count: int = 0) -> None:
        rooms = tuple(str(value or "").strip().lower() for value in tuple(room_resrefs or ()) if str(value or "").strip())
        selected = str(self.sky_traffic_room_combo.currentData() or "")
        self.sky_traffic_room_combo.blockSignals(True)
        try:
            self.sky_traffic_room_combo.clear()
            for room in rooms:
                self.sky_traffic_room_combo.addItem(room, room)
            index = self.sky_traffic_room_combo.findData(selected)
            self.sky_traffic_room_combo.setCurrentIndex(index if index >= 0 else (0 if rooms else -1))
        finally:
            self.sky_traffic_room_combo.blockSignals(False)
        self.sky_traffic_group.setEnabled(bool(rooms))
        self.sky_traffic_status_label.setText(
            f"{int(traffic_count)} authored flight actor(s). Models and cyan path arrows preview now. "
            "The KMAP contract targets room-MDL animloop1/2/3; export remains blocked until the generated controller graph "
            "matches the vanilla Taris/Dantooine/Telos fixtures and passes a manual game warp."
        )

    def set_world_settings(self, values: dict[str, Any] | None) -> None:
        """Refresh controls without emitting an edit request."""

        settings = dict(values or {})
        available = bool(settings.get("available", True))
        defaults = {
            "profile": "standard",
            "sun_ambient": (64, 64, 64),
            "sun_diffuse": (255, 255, 255),
            "dynamic_ambient": (64, 64, 64),
            "shadow_opacity": 50,
            "sun_shadows": False,
            "fog_enabled": False,
            "fog_color": (0, 0, 0),
            "fog_near": 100.0,
            "fog_far": 200.0,
        }
        merged = {**defaults, **settings}
        self._standard_values = {
            **defaults,
            **dict(settings.get("standard_values") or {}),
        }
        self._loading = True
        try:
            profile = str(merged["profile"] or "standard")
            index = self.profile_combo.findData(profile)
            self.profile_combo.setCurrentIndex(max(0, index))
            self._set_rgb(self.sun_ambient_spins, merged["sun_ambient"])
            self._set_rgb(self.sun_diffuse_spins, merged["sun_diffuse"])
            self._set_rgb(self.dynamic_ambient_spins, merged["dynamic_ambient"])
            self.shadow_opacity_spin.setValue(int(merged["shadow_opacity"]))
            self.sun_shadows_check.setChecked(bool(merged["sun_shadows"]))
            self.fog_enabled_check.setChecked(bool(merged["fog_enabled"]))
            self._set_rgb(self.fog_color_spins, merged["fog_color"])
            self.fog_near_spin.setValue(float(merged["fog_near"]))
            self.fog_far_spin.setValue(float(merged["fog_far"]))
            self._last_profile = profile
        finally:
            self._loading = False
        self.world_group.setEnabled(available)
        self.world_status_label.setText(
            "Sun ambient, sun diffuse, and dynamic ambient drive an approximate realtime preview on non-lightmapped "
            "surfaces; existing lightmaps remain baked. Fog and sun-shadow controls are ARE/export-only and are not "
            "previewed. A fresh manual KOTOR warp proof is still required."
            if available
            else "Create or import an authored Map Studio module before editing world settings."
        )
        self._update_profile_presentation()

    def _set_controls_from_baseline(self) -> None:
        baseline = self._standard_values
        self._set_rgb(self.sun_ambient_spins, baseline.get("sun_ambient"))
        self._set_rgb(self.sun_diffuse_spins, baseline.get("sun_diffuse"))
        self._set_rgb(self.dynamic_ambient_spins, baseline.get("dynamic_ambient"))
        self.shadow_opacity_spin.setValue(int(baseline.get("shadow_opacity", 50)))
        self.sun_shadows_check.setChecked(bool(baseline.get("sun_shadows", False)))
        self.fog_enabled_check.setChecked(bool(baseline.get("fog_enabled", False)))
        self._set_rgb(self.fog_color_spins, baseline.get("fog_color"))
        self.fog_near_spin.setValue(float(baseline.get("fog_near", 100.0)))
        self.fog_far_spin.setValue(float(baseline.get("fog_far", 200.0)))

    def _handle_profile_changed(self, _index: int = 0) -> None:
        profile = str(self.profile_combo.currentData() or "standard")
        if not self._loading:
            if profile == "fullbright" and self._last_profile != "fullbright":
                self._standard_values.update(self.world_settings())
                self._set_rgb(self.sun_ambient_spins, (255, 255, 255))
                self._set_rgb(self.sun_diffuse_spins, (255, 255, 255))
                self._set_rgb(self.dynamic_ambient_spins, (255, 255, 255))
                self.shadow_opacity_spin.setValue(0)
                self.sun_shadows_check.setChecked(False)
                self.fog_enabled_check.setChecked(False)
            elif self._last_profile == "fullbright" and profile != "fullbright":
                self._set_controls_from_baseline()
            self._last_profile = profile
        self._update_profile_presentation()

    def _update_profile_presentation(self) -> None:
        profile = str(self.profile_combo.currentData() or "standard")
        fullbright = profile == "fullbright"
        for widget in self._fullbright_overridden_widgets:
            widget.setEnabled(not fullbright)
        if fullbright:
            self.profile_hint.setText(
                "Fullbright Graybox forces white ambient/diffuse/dynamic light, zero shadows, and fog off at ARE compile time. "
                "The Standard/Custom baseline remains stored for restoration."
            )
        elif profile == "custom":
            self.profile_hint.setText("Custom writes the explicit RGB, shadow, and fog values below into the authored ARE.")
        else:
            self.profile_hint.setText("Standard / Match Module preserves loaded or authored KOTOR ARE lighting values.")

    def _emit_world_settings(self) -> None:
        self.worldSettingsRequested.emit(self.world_settings())

    def _emit_lightmap_apply(self) -> None:
        self.lightmapApplyRequested.emit(self.lightmap_settings())

    def _emit_skybox_create(self) -> None:
        self.skyboxCreateRequested.emit(self.skybox_settings())

    def _emit_sky_panorama(self) -> None:
        self.skyPanoramaRequested.emit(self.skybox_settings())

    def _emit_sky_traffic_create(self) -> None:
        self.skyTrafficCreateRequested.emit(self.sky_traffic_settings())

    def apply_ghost_theme(self, _theme: object) -> None:
        """Native Qt controls inherit the active theme from the Map Studio window."""

        self.update()

    def apply_ghost_layout(self, _layout: object) -> None:
        """Expose a stable panel layout hook without hardcoded workbench dimensions."""

        self.updateGeometry()


__all__ = ["MapStudioEnvironmentTab"]
