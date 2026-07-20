"""Selection properties panel for KMAP objects."""

from __future__ import annotations

from collections.abc import Mapping

from PySide6 import QtCore, QtWidgets

from src.core.level import KMapProject, LevelTransform


def _pie_context_value(row: object, name: str, default: object = "") -> object:
    """Read a dialogue-catalog field from either its dataclass or mapping form."""

    if isinstance(row, Mapping):
        return row.get(name, default)
    return getattr(row, name, default)


class MapStudioPIEContextPanel(QtWidgets.QWidget):
    """Compact, resource-driven preview context for Map Studio PIE dialogue."""

    playerContextChanged = QtCore.Signal(str, str)
    starterOverrideChanged = QtCore.Signal(str, str, str)
    previewRequested = QtCore.Signal(str, str)
    resetRequested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MapStudioPIEContextPanel")
        self._catalog: tuple[object, ...] = ()
        self._overrides: dict[str, dict[str, str]] = {}
        self._stale_override_resrefs: set[str] = set()
        self._syncing = False

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        title = QtWidgets.QLabel("Conversation Context")
        title.setProperty("heading", True)
        root.addWidget(title)

        hint = QtWidgets.QLabel(
            "Choose the simulated player context and, when needed, preview a specific authored dialogue start."
        )
        hint.setObjectName("mapStudioPIEContextHintLabel")
        hint.setWordWrap(True)
        root.addWidget(hint)

        form = QtWidgets.QFormLayout()
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        root.addLayout(form)

        self.player_context_combo = QtWidgets.QComboBox()
        self.player_context_combo.setObjectName("mapStudioPIEPlayerContextComboBox")
        self.player_context_combo.addItem("Normal player character", "normal_pc")
        self.player_context_combo.addItem("B-4D4 protocol droid", "b4d4")
        self.player_context_combo.setToolTip(
            "Sets the PIE player role used when evaluating dialogue Active scripts."
        )
        form.addRow("Player", self.player_context_combo)

        self.gender_combo = QtWidgets.QComboBox()
        self.gender_combo.setObjectName("mapStudioPIEGenderComboBox")
        self.gender_combo.addItem("Male", "male")
        self.gender_combo.addItem("Female", "female")
        self.gender_combo.setToolTip(
            "Sets the PIE player gender used by dialogue condition scripts such as c_ismale and c_isfemale."
        )
        form.addRow("Gender", self.gender_combo)

        self.conversation_combo = QtWidgets.QComboBox()
        self.conversation_combo.setObjectName("mapStudioPIEConversationComboBox")
        self.conversation_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.conversation_combo.setMinimumContentsLength(18)
        form.addRow("Conversation", self.conversation_combo)

        self.starter_combo = QtWidgets.QComboBox()
        self.starter_combo.setObjectName("mapStudioPIEStarterComboBox")
        self.starter_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.starter_combo.setMinimumContentsLength(18)
        form.addRow("Start", self.starter_combo)

        self.source_label = QtWidgets.QLabel("")
        self.source_label.setObjectName("mapStudioPIEContextSourceLabel")
        self.source_label.setWordWrap(True)
        form.addRow("Source", self.source_label)

        self.opening_preview_label = QtWidgets.QLabel("")
        self.opening_preview_label.setObjectName("mapStudioPIEContextOpeningPreviewLabel")
        self.opening_preview_label.setWordWrap(True)
        self.opening_preview_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.opening_preview_label.setToolTip(
            "The authored NPC line this conversation opens with under the current PIE context. "
            "Resolved by the same dialogue evaluator the live PIE runtime uses."
        )
        form.addRow("Opens with", self.opening_preview_label)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setObjectName("mapStudioPIEContextStatusLabel")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.reset_button = QtWidgets.QPushButton("Reset to clean PIE context")
        self.reset_button.setObjectName("mapStudioPIEContextResetButton")
        self.reset_button.setToolTip(
            "Use a normal male player, clear preview globals, and return every conversation to canonical Auto selection."
        )
        root.addWidget(self.reset_button)
        root.addStretch(1)

        self.player_context_combo.currentIndexChanged.connect(self._emit_player_context)
        self.gender_combo.currentIndexChanged.connect(self._emit_player_context)
        self.conversation_combo.currentIndexChanged.connect(self._conversation_changed)
        self.starter_combo.currentIndexChanged.connect(self._starter_changed)
        self.reset_button.clicked.connect(lambda _checked=False: self.resetRequested.emit())

    def set_catalog(
        self,
        catalog: object,
        *,
        player_role: str = "normal_pc",
        player_gender: str = "male",
        overrides: object = None,
        selected_conversation_resref: str = "",
        unavailable_reason: str = "",
    ) -> None:
        """Replace tuneable choices with the resources available to the loaded project."""

        current_resref = str(
            selected_conversation_resref
            or self.conversation_combo.currentData()
            or ""
        ).strip().lower()
        self._catalog = tuple(catalog or ())
        self._overrides = self._normalize_overrides(overrides)
        self._stale_override_resrefs.clear()
        self._syncing = True
        try:
            self._set_combo_data(self.player_context_combo, player_role, "normal_pc")
            self._set_combo_data(self.gender_combo, player_gender, "male")
            self.conversation_combo.clear()
            for conversation in self._catalog:
                resref = str(_pie_context_value(conversation, "conversation_resref", "") or "").strip().lower()
                if not resref:
                    continue
                display_name = str(_pie_context_value(conversation, "display_name", "") or "").strip()
                label = display_name if display_name and display_name.lower() != resref else resref
                if display_name and display_name.lower() != resref:
                    label = f"{display_name} [{resref}]"
                self.conversation_combo.addItem(label, resref)
                index = self.conversation_combo.count() - 1
                owners = tuple(_pie_context_value(conversation, "owner_names", ()) or ())
                source = str(_pie_context_value(conversation, "source_label", "") or "").strip()
                tooltip_parts = [f"DLG resource: {resref}"]
                if owners:
                    tooltip_parts.append("Used by: " + ", ".join(str(value) for value in owners if str(value)))
                if source:
                    tooltip_parts.append("Source: " + source)
                self.conversation_combo.setItemData(index, "\n".join(tooltip_parts), QtCore.Qt.ToolTipRole)
            wanted_index = self.conversation_combo.findData(current_resref)
            self.conversation_combo.setCurrentIndex(wanted_index if wanted_index >= 0 else 0)
            available = self.conversation_combo.count() > 0
            self.conversation_combo.setEnabled(available)
            self.starter_combo.setEnabled(available)
            self._populate_starters()
            if available:
                self._update_status_text()
            else:
                self.source_label.clear()
                self.clear_opening_preview()
                self.status_label.setText(
                    unavailable_reason
                    or "No dialogue resources are available. A bare .lyt contains room layout only; "
                    "attach or import a .mod or hydrated .kmap to tune conversation starts."
                )
        finally:
            self._syncing = False

    def current_starter_link_id(self) -> str:
        """Return the currently selected starter link id ('' means Auto)."""

        return str(self.starter_combo.currentData() or "").strip().lower()

    def clear_opening_preview(self) -> None:
        self.opening_preview_label.setText("")

    def set_opening_preview(
        self,
        text: str,
        *,
        forced: bool = False,
        blocked: bool = False,
        warning: str = "",
    ) -> None:
        """Show the resolved opening NPC line for the selected conversation/start."""

        clean = str(text or "").strip()
        if blocked or (not clean and warning):
            self.opening_preview_label.setText(str(warning or "This conversation has no valid starting entry.").strip())
            return
        if not clean:
            self.opening_preview_label.setText("")
            return
        prefix = "Forced preview start" if forced else "Auto"
        display = clean if len(clean) <= 200 else clean[:197].rstrip() + "..."
        self.opening_preview_label.setText(f"[{prefix}] {display}")

    def focus_conversation_for_owner(self, owner_id: str) -> bool:
        """Select the conversation owned by the chosen creature/placeable, if any."""

        wanted = str(owner_id or "").strip().lower()
        if not wanted:
            return False
        for conversation in self._catalog:
            owner_ids = tuple(_pie_context_value(conversation, "owner_ids", ()) or ())
            if wanted not in {str(value or "").strip().lower() for value in owner_ids}:
                continue
            resref = str(_pie_context_value(conversation, "conversation_resref", "") or "").strip().lower()
            index = self.conversation_combo.findData(resref)
            if index < 0:
                return False
            blocked = self.conversation_combo.blockSignals(True)
            try:
                self.conversation_combo.setCurrentIndex(index)
            finally:
                self.conversation_combo.blockSignals(blocked)
            self._populate_starters()
            return True
        return False

    def _conversation_for_resref(self, resref: str) -> object | None:
        wanted = str(resref or "").strip().lower()
        return next(
            (
                row
                for row in self._catalog
                if str(_pie_context_value(row, "conversation_resref", "") or "").strip().lower() == wanted
            ),
            None,
        )

    def _populate_starters(self) -> None:
        resref = str(self.conversation_combo.currentData() or "").strip().lower()
        conversation = self._conversation_for_resref(resref)
        blocked = self.starter_combo.blockSignals(True)
        try:
            self.starter_combo.clear()
            if conversation is None:
                self.source_label.clear()
                return
            self.starter_combo.addItem("Auto (clean PIE state)", "")
            self.starter_combo.setItemData(
                0,
                "Evaluate supported authored Active conditions in StartingList order. "
                "Unsupported script conditions remain unknown in PIE.",
                QtCore.Qt.ToolTipRole,
            )
            for ordinal, starter in enumerate(tuple(_pie_context_value(conversation, "starters", ()) or ()), start=1):
                link_id = str(_pie_context_value(starter, "link_id", "") or "").strip()
                if not link_id:
                    continue
                label = str(_pie_context_value(starter, "label", "") or "").strip()
                text = str(_pie_context_value(starter, "text", "") or "").strip()
                speaker = str(_pie_context_value(starter, "speaker_tag", "") or "").strip()
                conditions = tuple(_pie_context_value(starter, "condition_resrefs", ()) or ())
                short = label or text or f"Starting link {ordinal}"
                if len(short) > 72:
                    short = short[:69].rstrip() + "..."
                self.starter_combo.addItem(f"Preview override — {short}", link_id)
                index = self.starter_combo.count() - 1
                details = ["PIE preview override: bypasses this starting link's Active conditions."]
                if speaker:
                    details.append(f"Speaker: {speaker}")
                if text:
                    details.append(text)
                if conditions:
                    details.append("Active: " + ", ".join(str(value) for value in conditions if str(value)))
                details.append(f"Link: {link_id}")
                self.starter_combo.setItemData(index, "\n".join(details), QtCore.Qt.ToolTipRole)
            override = self._overrides.get(resref, {})
            override_link = str(override.get("starter_link_id") or "")
            override_sha = str(override.get("resource_sha256") or "").strip().lower()
            current_sha = str(_pie_context_value(conversation, "resource_sha256", "") or "").strip().lower()
            if override_link and override_sha and current_sha and override_sha != current_sha:
                self._stale_override_resrefs.add(resref)
                override_link = ""
            else:
                self._stale_override_resrefs.discard(resref)
            selected_index = self.starter_combo.findData(override_link)
            self.starter_combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
            source = str(_pie_context_value(conversation, "source_label", "") or "").strip()
            owner_names = tuple(_pie_context_value(conversation, "owner_names", ()) or ())
            source_parts = [source] if source else [f"{resref}.dlg"]
            if owner_names:
                source_parts.append("Used by " + ", ".join(str(value) for value in owner_names if str(value)))
            self.source_label.setText("; ".join(source_parts))
        finally:
            self.starter_combo.blockSignals(blocked)

    def _conversation_changed(self, _index: int) -> None:
        self._populate_starters()
        if self.conversation_combo.count() > 0:
            self._update_status_text()
        if not self._syncing:
            resref = str(self.conversation_combo.currentData() or "").strip().lower()
            if resref:
                self.previewRequested.emit(resref, self.current_starter_link_id())

    def _update_status_text(self) -> None:
        resref = str(self.conversation_combo.currentData() or "").strip().lower()
        if resref in self._stale_override_resrefs:
            self.status_label.setText(
                "This DLG changed after its preview start was saved, so PIE safely returned it to Auto. "
                "Choose a new preview override if needed."
            )
            return
        self.status_label.setText(
            "Auto (clean PIE state) follows authored StartingList order and evaluates supported Active conditions. "
            "A specific start is a PIE-only preview override."
        )

    def _emit_player_context(self, _index: int) -> None:
        if self._syncing:
            return
        self.playerContextChanged.emit(
            str(self.player_context_combo.currentData() or "normal_pc"),
            str(self.gender_combo.currentData() or "male"),
        )

    def _starter_changed(self, _index: int) -> None:
        if self._syncing:
            return
        resref = str(self.conversation_combo.currentData() or "").strip().lower()
        conversation = self._conversation_for_resref(resref)
        if conversation is None:
            return
        link_id = str(self.starter_combo.currentData() or "").strip()
        resource_sha = str(_pie_context_value(conversation, "resource_sha256", "") or "").strip().lower()
        self.starterOverrideChanged.emit(resref, link_id, resource_sha)

    @staticmethod
    def _set_combo_data(combo: QtWidgets.QComboBox, value: object, fallback: object) -> None:
        index = combo.findData(str(value or "").strip().lower())
        if index < 0:
            index = combo.findData(fallback)
        combo.setCurrentIndex(max(0, index))

    @staticmethod
    def _normalize_overrides(overrides: object) -> dict[str, dict[str, str]]:
        if not isinstance(overrides, Mapping):
            return {}
        normalized: dict[str, dict[str, str]] = {}
        for key, value in overrides.items():
            resref = str(key or "").strip().lower()
            if not resref or not isinstance(value, Mapping):
                continue
            normalized[resref] = {
                "starter_link_id": str(value.get("starter_link_id") or "").strip(),
                "resource_sha256": str(value.get("resource_sha256") or "").strip().lower(),
            }
        return normalized


class ModuleEditorPropertiesPanel(QtWidgets.QWidget):
    transformChanged = QtCore.Signal(str, object)
    visibilityChanged = QtCore.Signal(str, bool)
    lockChanged = QtCore.Signal(str, bool)
    propertyChanged = QtCore.Signal(str, str, object)
    transitionChanged = QtCore.Signal(str, str, str, int, int)
    cameraChanged = QtCore.Signal(str, int, float, float, float, float)
    roomLightChanged = QtCore.Signal(str, object)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ModuleEditorPropertiesPanel")
        self._project: KMapProject | None = None
        self._authored_placements: dict[str, object] = {}
        self._authored_room_lights: dict[str, object] = {}
        self._item_id = ""
        root = QtWidgets.QVBoxLayout(self)
        self.title = QtWidgets.QLabel("No Selection")
        self.title.setProperty("heading", True)
        root.addWidget(self.title)
        self.form = QtWidgets.QFormLayout()
        root.addLayout(self.form)
        self.name_edit = QtWidgets.QLineEdit()
        self.form.addRow("Name", self.name_edit)
        self.source_label = QtWidgets.QLabel("")
        self.form.addRow("Source", self.source_label)
        self.visible_box = QtWidgets.QCheckBox("Visible")
        self.locked_box = QtWidgets.QCheckBox("Locked")
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.visible_box)
        row.addWidget(self.locked_box)
        self.form.addRow("State", row)
        self.position = self._vector_row("Position")
        self.rotation = self._vector_row("Rotation")
        self.scale = self._vector_row("Scale")
        self.transition_group = QtWidgets.QGroupBox("Transition")
        self.transition_group.setObjectName("mapStudioTransitionPropertiesGroup")
        transition_layout = QtWidgets.QFormLayout(self.transition_group)
        self.transition_linked_to_edit = QtWidgets.QLineEdit()
        self.transition_linked_to_edit.setObjectName("mapStudioTransitionLinkedToLineEdit")
        self.transition_linked_to_edit.setPlaceholderText("destination tag or waypoint")
        self.transition_module_edit = QtWidgets.QLineEdit()
        self.transition_module_edit.setObjectName("mapStudioTransitionLinkedModuleLineEdit")
        self.transition_module_edit.setPlaceholderText("optional module resref")
        self.transition_target_type_combo = QtWidgets.QComboBox()
        self.transition_target_type_combo.setObjectName("mapStudioTransitionTargetTypeComboBox")
        self.transition_target_type_combo.addItem("No engine link", 0)
        self.transition_target_type_combo.addItem("Destination door", 1)
        self.transition_target_type_combo.addItem("Destination waypoint", 2)
        self.transition_target_type_combo.setToolTip(
            "KOTOR LinkedToFlags: choose whether Linked To names a door (1) or waypoint (2)."
        )
        self.transition_destination_spin = QtWidgets.QSpinBox()
        self.transition_destination_spin.setObjectName("mapStudioTransitionDestinationSpinBox")
        self.transition_destination_spin.setRange(0, 2147483647)
        self.transition_destination_spin.setSpecialValueText("Use area name")
        self.transition_destination_spin.setToolTip(
            "Optional dialog.tlk StringRef displayed as the destination name. This does not choose the target type."
        )
        transition_layout.addRow("Linked To", self.transition_linked_to_edit)
        transition_layout.addRow("Module", self.transition_module_edit)
        transition_layout.addRow("Target type", self.transition_target_type_combo)
        transition_layout.addRow("Destination name StringRef", self.transition_destination_spin)
        root.addWidget(self.transition_group)
        self.camera_group = QtWidgets.QGroupBox("Camera")
        self.camera_group.setObjectName("mapStudioCameraPropertiesGroup")
        camera_layout = QtWidgets.QFormLayout(self.camera_group)
        self.camera_hint_label = QtWidgets.QLabel(
            "Camera exports to the module GIT CameraList. Position is edited above; these fields control CameraID, FOV, listener range, and pitch."
        )
        self.camera_hint_label.setObjectName("mapStudioCameraPropertiesHintLabel")
        self.camera_hint_label.setWordWrap(True)
        self.camera_id_spin = QtWidgets.QSpinBox()
        self.camera_id_spin.setObjectName("mapStudioCameraIdSpinBox")
        self.camera_id_spin.setRange(0, 2147483647)
        self.camera_fov_spin = self._light_spin("mapStudioCameraFieldOfViewSpinBox", 0.0, 179.0, 45.0)
        self.camera_height_spin = self._light_spin("mapStudioCameraHeightSpinBox", -1000000.0, 1000000.0, 0.0)
        self.camera_mic_range_spin = self._light_spin("mapStudioCameraMicRangeSpinBox", 0.0, 1000000.0, 0.0)
        self.camera_pitch_spin = self._light_spin("mapStudioCameraPitchSpinBox", -360.0, 360.0, 0.0)
        camera_layout.addRow(self.camera_hint_label)
        camera_layout.addRow("Camera ID", self.camera_id_spin)
        camera_layout.addRow("Field of View", self.camera_fov_spin)
        camera_layout.addRow("Height", self.camera_height_spin)
        camera_layout.addRow("Mic Range", self.camera_mic_range_spin)
        camera_layout.addRow("Pitch", self.camera_pitch_spin)
        root.addWidget(self.camera_group)
        self.room_light_group = QtWidgets.QGroupBox("Room Light")
        self.room_light_group.setObjectName("mapStudioRoomLightPropertiesGroup")
        light_layout = QtWidgets.QFormLayout(self.room_light_group)
        self.room_light_type_combo = QtWidgets.QComboBox()
        self.room_light_type_combo.setObjectName("mapStudioRoomLightTypeComboBox")
        self.room_light_type_combo.addItem("Point", "point")
        self.room_light_type_combo.addItem("Spot", "spot")
        self.room_light_type_combo.addItem("Ambient", "ambient")
        self.room_light_color_r_spin = self._light_spin("mapStudioRoomLightColorRSpinBox", 0.0, 1.0, 1.0)
        self.room_light_color_g_spin = self._light_spin("mapStudioRoomLightColorGSpinBox", 0.0, 1.0, 0.92)
        self.room_light_color_b_spin = self._light_spin("mapStudioRoomLightColorBSpinBox", 0.0, 1.0, 0.78)
        color_row = QtWidgets.QHBoxLayout()
        color_row.addWidget(self.room_light_color_r_spin)
        color_row.addWidget(self.room_light_color_g_spin)
        color_row.addWidget(self.room_light_color_b_spin)
        self.room_light_radius_spin = self._light_spin("mapStudioRoomLightRadiusSpinBox", 0.01, 1000.0, 8.0)
        self.room_light_intensity_spin = self._light_spin("mapStudioRoomLightIntensitySpinBox", 0.0, 100.0, 1.0)
        self.room_light_enabled_check = QtWidgets.QCheckBox("Enabled in viewport and bake")
        self.room_light_enabled_check.setObjectName("mapStudioRoomLightEnabledCheckBox")
        self.room_light_casts_shadows_check = QtWidgets.QCheckBox("Cast baked shadows")
        self.room_light_casts_shadows_check.setObjectName("mapStudioRoomLightCastsShadowsCheckBox")
        self.room_light_affects_diffuse_check = QtWidgets.QCheckBox("Affect realtime diffuse preview")
        self.room_light_affects_diffuse_check.setObjectName("mapStudioRoomLightAffectsDiffuseCheckBox")
        self.room_light_affects_lightmap_check = QtWidgets.QCheckBox("Include in lightmap bake")
        self.room_light_affects_lightmap_check.setObjectName("mapStudioRoomLightAffectsLightmapCheckBox")
        self.room_light_direction_spins = tuple(
            self._light_spin(f"mapStudioRoomLightDirection{axis}SpinBox", -1.0, 1.0, value)
            for axis, value in (("X", 0.0), ("Y", 0.0), ("Z", -1.0))
        )
        direction_row = QtWidgets.QHBoxLayout()
        for spin in self.room_light_direction_spins:
            direction_row.addWidget(spin)
        self.room_light_cone_spin = self._light_spin("mapStudioRoomLightConeAngleSpinBox", 1.0, 179.0, 45.0)
        self.room_light_cone_spin.setSuffix(" deg")
        self.room_light_bake_group_edit = QtWidgets.QLineEdit()
        self.room_light_bake_group_edit.setObjectName("mapStudioRoomLightBakeGroupLineEdit")
        self.room_light_bake_group_edit.setMaxLength(32)
        self.room_light_bake_group_edit.setPlaceholderText("optional bake set")
        light_layout.addRow("Type", self.room_light_type_combo)
        light_layout.addRow("Color RGB", color_row)
        light_layout.addRow("Radius", self.room_light_radius_spin)
        light_layout.addRow("Intensity", self.room_light_intensity_spin)
        light_layout.addRow("State", self.room_light_enabled_check)
        light_layout.addRow("Shadows", self.room_light_casts_shadows_check)
        light_layout.addRow("Diffuse", self.room_light_affects_diffuse_check)
        light_layout.addRow("Lightmap", self.room_light_affects_lightmap_check)
        light_layout.addRow("Spot direction XYZ", direction_row)
        light_layout.addRow("Spot cone", self.room_light_cone_spin)
        light_layout.addRow("Bake group", self.room_light_bake_group_edit)
        root.addWidget(self.room_light_group)
        root.addStretch(1)
        self.name_edit.editingFinished.connect(self._name_changed)
        self.visible_box.toggled.connect(lambda value: self.visibilityChanged.emit(self._item_id, value))
        self.locked_box.toggled.connect(lambda value: self.lockChanged.emit(self._item_id, value))
        for spin in (*self.position, *self.rotation, *self.scale):
            spin.valueChanged.connect(lambda _value: self._transform_changed())
        self.transition_linked_to_edit.editingFinished.connect(self._transition_changed)
        self.transition_module_edit.editingFinished.connect(self._transition_changed)
        self.transition_target_type_combo.currentIndexChanged.connect(lambda _index: self._transition_changed())
        self.transition_destination_spin.valueChanged.connect(lambda _value: self._transition_changed())
        self.camera_id_spin.valueChanged.connect(lambda _value: self._camera_changed())
        for spin in (self.camera_fov_spin, self.camera_height_spin, self.camera_mic_range_spin, self.camera_pitch_spin):
            spin.valueChanged.connect(lambda _value: self._camera_changed())
        self.room_light_type_combo.currentIndexChanged.connect(lambda _index: self._room_light_type_changed())
        for spin in (
            self.room_light_color_r_spin,
            self.room_light_color_g_spin,
            self.room_light_color_b_spin,
            self.room_light_radius_spin,
            self.room_light_intensity_spin,
            *self.room_light_direction_spins,
            self.room_light_cone_spin,
        ):
            spin.valueChanged.connect(lambda _value: self._room_light_changed())
        for check in (
            self.room_light_enabled_check,
            self.room_light_casts_shadows_check,
            self.room_light_affects_diffuse_check,
            self.room_light_affects_lightmap_check,
        ):
            check.toggled.connect(lambda _value: self._room_light_changed())
        self.room_light_bake_group_edit.editingFinished.connect(self._room_light_changed)
        self.transition_group.setVisible(False)
        self.camera_group.setVisible(False)
        self.room_light_group.setVisible(False)

    def set_project(self, project: KMapProject, authored_gameplay_placements=(), authored_room_lights=()) -> None:
        self._project = project
        self._authored_placements = {
            str(getattr(row, "placement_id", "") or ""): row
            for row in authored_gameplay_placements or ()
            if str(getattr(row, "placement_id", "") or "")
        }
        self._authored_room_lights = {
            str(getattr(row, "light_id", "") or ""): row
            for row in authored_room_lights or ()
            if str(getattr(row, "light_id", "") or "")
        }

    def current_item_id(self) -> str:
        """Return the item whose values the Details panel is currently showing."""

        return str(getattr(self, "_item_id", "") or "")

    def set_selection(self, item_id: str) -> None:
        self._item_id = item_id
        project = self._project
        item = (project.find_room(item_id) or project.find_module(item_id) or project.find_blueprint(item_id)) if project else None
        authored = self._authored_placements.get(item_id)
        authored_light = self._authored_room_lights.get(item_id)
        self.setEnabled(item is not None or authored is not None or authored_light is not None)
        if item is None and authored is None and authored_light is None:
            self.title.setText("No Selection")
            self.transition_group.setVisible(False)
            self.camera_group.setVisible(False)
            self.room_light_group.setVisible(False)
            return
        self.blockSignals(True)
        for widget in (self.name_edit, self.visible_box, self.locked_box, *self.position, *self.rotation, *self.scale):
            widget.setEnabled(True)
        self.transition_group.setVisible(False)
        self.camera_group.setVisible(False)
        self.room_light_group.setVisible(False)
        if authored is not None:
            kind_key = str(getattr(authored, "kind", "object") or "object").lower()
            kind = kind_key.title()
            tag = str(getattr(authored, "tag", "") or getattr(authored, "template_resref", "") or item_id)
            is_spatial = bool(getattr(authored, "is_spatial", True))
            self.title.setText(f"Authored {kind} Placement")
            self.name_edit.setText(tag)
            self.name_edit.setEnabled(kind_key != "camera")
            scope = "spatial placement" if is_spatial else "module-level resource"
            transition = str(getattr(authored, "transition_summary", "") or "")
            source_text = (
                f"{str(getattr(authored, 'template_resref', '') or '(no template)')} "
                f"[{str(getattr(authored, 'kind', 'object') or 'object')}; {scope}]"
            )
            if transition:
                source_text = f"{source_text} - {transition}"
            self.source_label.setText(source_text)
            self.visible_box.setChecked(True)
            self.locked_box.setChecked(False)
            self.visible_box.setEnabled(False)
            self.locked_box.setEnabled(False)
            self._set_vector(self.position, getattr(authored, "position", (0.0, 0.0, 0.0)))
            self._set_vector(self.rotation, (0.0, 0.0, float(getattr(authored, "bearing", 0.0) or 0.0)))
            self._set_vector(self.scale, (1.0, 1.0, 1.0))
            for spin in (*self.position, *self.rotation):
                spin.setEnabled(is_spatial)
            if kind_key == "camera":
                for spin in self.rotation:
                    spin.setEnabled(False)
            for spin in self.scale:
                spin.setEnabled(False)
            transition_capable = bool(getattr(authored, "transition_capable", False))
            self.transition_group.setVisible(transition_capable)
            self.transition_linked_to_edit.setText(str(getattr(authored, "linked_to", "") or ""))
            self.transition_module_edit.setText(str(getattr(authored, "linked_to_module", "") or ""))
            target_index = self.transition_target_type_combo.findData(int(getattr(authored, "linked_to_flags", 0) or 0))
            self.transition_target_type_combo.setCurrentIndex(target_index if target_index >= 0 else 0)
            self.transition_destination_spin.setValue(int(getattr(authored, "transition_destination", 0) or 0))
            if kind_key == "camera":
                self._set_camera_values(authored)
                self.camera_group.setVisible(True)
            self.blockSignals(False)
            return
        if authored_light is not None:
            self.title.setText("Authored Room Light")
            self.name_edit.setText(str(getattr(authored_light, "name", "") or item_id))
            self.name_edit.setEnabled(True)
            self.source_label.setText(
                f"{getattr(authored_light, 'light_type', 'point')} in {getattr(authored_light, 'room_resref', '')}; "
                f"radius {float(getattr(authored_light, 'radius', 0.0) or 0.0):.2f}, "
                f"intensity {float(getattr(authored_light, 'intensity', 0.0) or 0.0):.2f}"
            )
            self.visible_box.setChecked(True)
            self.locked_box.setChecked(False)
            self.visible_box.setEnabled(False)
            self.locked_box.setEnabled(False)
            self._set_vector(self.position, getattr(authored_light, "position", (0.0, 0.0, 0.0)))
            self._set_vector(self.rotation, (0.0, 0.0, 0.0))
            self._set_vector(self.scale, (1.0, 1.0, 1.0))
            for spin in (*self.rotation, *self.scale):
                spin.setEnabled(False)
            self._set_room_light_values(authored_light)
            self.room_light_group.setVisible(True)
            self.blockSignals(False)
            return
        kind = "Blueprint" if hasattr(item, "blueprint_id") else "Room" if hasattr(item, "room_id") else "Module"
        self.title.setText(f"{kind} Properties")
        self.name_edit.setText(getattr(item, "name", getattr(item, "module_name", "")))
        self.source_label.setText(getattr(item, "source_path", getattr(item, "source_module", getattr(item, "template_resref", ""))) or "")
        self.visible_box.setChecked(bool(getattr(item, "visible", True)))
        self.locked_box.setChecked(bool(getattr(item, "locked", False)))
        transform = getattr(item, "transform", None)
        if transform is None:
            transform = LevelTransform(position=getattr(item, "position", (0.0, 0.0, 0.0)), rotation=getattr(item, "rotation", (0.0, 0.0, 0.0)))
        self._set_vector(self.position, transform.position)
        self._set_vector(self.rotation, transform.rotation)
        self._set_vector(self.scale, transform.scale)
        self.transition_group.setVisible(False)
        self.camera_group.setVisible(False)
        self.room_light_group.setVisible(False)
        self.blockSignals(False)

    def _vector_row(self, label: str) -> tuple[QtWidgets.QDoubleSpinBox, QtWidgets.QDoubleSpinBox, QtWidgets.QDoubleSpinBox]:
        boxes = tuple(QtWidgets.QDoubleSpinBox() for _ in range(3))
        row = QtWidgets.QHBoxLayout()
        for box in boxes:
            box.setRange(-1000000.0, 1000000.0)
            box.setDecimals(3)
            box.setSingleStep(1.0)
            row.addWidget(box)
        self.form.addRow(label, row)
        return boxes

    def _light_spin(self, object_name: str, minimum: float, maximum: float, value: float) -> QtWidgets.QDoubleSpinBox:
        box = QtWidgets.QDoubleSpinBox()
        box.setObjectName(object_name)
        box.setRange(minimum, maximum)
        box.setDecimals(3)
        box.setSingleStep(0.1)
        box.setValue(value)
        return box

    @staticmethod
    def _set_vector(boxes, values) -> None:
        for box, value in zip(boxes, values):
            box.setValue(float(value))

    def _vector(self, boxes) -> tuple[float, float, float]:
        return tuple(float(box.value()) for box in boxes)  # type: ignore[return-value]

    def _transform_changed(self) -> None:
        if self.signalsBlocked() or not self._item_id:
            return
        self.transformChanged.emit(
            self._item_id,
            LevelTransform(position=self._vector(self.position), rotation=self._vector(self.rotation), scale=self._vector(self.scale)),
        )

    def _name_changed(self) -> None:
        if self._item_id:
            self.propertyChanged.emit(self._item_id, "name", self.name_edit.text().strip())

    def _transition_changed(self) -> None:
        if self.signalsBlocked() or not self._item_id or not self.transition_group.isVisible():
            return
        self.transitionChanged.emit(
            self._item_id,
            self.transition_linked_to_edit.text().strip(),
            self.transition_module_edit.text().strip(),
            int(self.transition_target_type_combo.currentData() or 0),
            int(self.transition_destination_spin.value()),
        )

    def _set_camera_values(self, authored: object) -> None:
        try:
            camera_id = int(str(getattr(authored, "camera_id", getattr(authored, "tag", 0)) or 0), 10)
        except (TypeError, ValueError):
            camera_id = 0
        self.camera_id_spin.setValue(max(0, camera_id))
        self.camera_fov_spin.setValue(float(getattr(authored, "field_of_view", 45.0) or 0.0))
        self.camera_height_spin.setValue(float(getattr(authored, "height", 0.0) or 0.0))
        self.camera_mic_range_spin.setValue(float(getattr(authored, "mic_range", 0.0) or 0.0))
        self.camera_pitch_spin.setValue(float(getattr(authored, "pitch", 0.0) or 0.0))

    def _camera_changed(self) -> None:
        if self.signalsBlocked() or not self._item_id or not self.camera_group.isVisible():
            return
        self.cameraChanged.emit(
            self._item_id,
            int(self.camera_id_spin.value()),
            float(self.camera_fov_spin.value()),
            float(self.camera_height_spin.value()),
            float(self.camera_mic_range_spin.value()),
            float(self.camera_pitch_spin.value()),
        )

    def _set_room_light_values(self, authored_light: object) -> None:
        light_type = str(getattr(authored_light, "light_type", "point") or "point").lower()
        index = self.room_light_type_combo.findData(light_type)
        if index < 0:
            index = self.room_light_type_combo.findData("point")
        self.room_light_type_combo.setCurrentIndex(index)
        color = getattr(authored_light, "color", (1.0, 0.92, 0.78))
        self.room_light_color_r_spin.setValue(float(color[0]))
        self.room_light_color_g_spin.setValue(float(color[1]))
        self.room_light_color_b_spin.setValue(float(color[2]))
        self.room_light_radius_spin.setValue(float(getattr(authored_light, "radius", 8.0) or 8.0))
        self.room_light_intensity_spin.setValue(float(getattr(authored_light, "intensity", 1.0) or 1.0))
        self.room_light_enabled_check.setChecked(bool(getattr(authored_light, "enabled", True)))
        self.room_light_casts_shadows_check.setChecked(bool(getattr(authored_light, "casts_shadows", True)))
        self.room_light_affects_diffuse_check.setChecked(bool(getattr(authored_light, "affects_diffuse", True)))
        self.room_light_affects_lightmap_check.setChecked(bool(getattr(authored_light, "affects_lightmap", True)))
        self._set_vector(self.room_light_direction_spins, getattr(authored_light, "direction", (0.0, 0.0, -1.0)))
        self.room_light_cone_spin.setValue(float(getattr(authored_light, "cone_angle_degrees", 45.0) or 45.0))
        self.room_light_bake_group_edit.setText(str(getattr(authored_light, "bake_group", "") or ""))
        self._sync_room_light_type_controls()

    def _room_light_type_changed(self) -> None:
        self._sync_room_light_type_controls()
        self._room_light_changed()

    def _sync_room_light_type_controls(self) -> None:
        is_spot = str(self.room_light_type_combo.currentData() or "point") == "spot"
        for spin in self.room_light_direction_spins:
            spin.setEnabled(is_spot)
        self.room_light_cone_spin.setEnabled(is_spot)

    def _room_light_changed(self) -> None:
        if self.signalsBlocked() or not self._item_id or not self.room_light_group.isVisible():
            return
        self.roomLightChanged.emit(
            self._item_id,
            {
                "light_type": str(self.room_light_type_combo.currentData() or "point"),
                "color": (
                float(self.room_light_color_r_spin.value()),
                float(self.room_light_color_g_spin.value()),
                float(self.room_light_color_b_spin.value()),
                ),
                "radius": float(self.room_light_radius_spin.value()),
                "intensity": float(self.room_light_intensity_spin.value()),
                "enabled": bool(self.room_light_enabled_check.isChecked()),
                "casts_shadows": bool(self.room_light_casts_shadows_check.isChecked()),
                "affects_diffuse": bool(self.room_light_affects_diffuse_check.isChecked()),
                "affects_lightmap": bool(self.room_light_affects_lightmap_check.isChecked()),
                "direction": self._vector(self.room_light_direction_spins),
                "cone_angle_degrees": float(self.room_light_cone_spin.value()),
                "bake_group": self.room_light_bake_group_edit.text().strip() or None,
            },
        )
