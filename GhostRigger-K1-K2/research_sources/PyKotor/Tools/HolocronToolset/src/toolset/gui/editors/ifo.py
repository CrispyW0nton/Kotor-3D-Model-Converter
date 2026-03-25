"""Editor for module info (IFO) files."""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtWidgets import QComboBox, QLineEdit

from pykotor.common.misc import ResRef
from pykotor.resource.formats.gff import write_gff
from pykotor.resource.generics.ifo import IFO, dismantle_ifo, read_ifo
from pykotor.resource.type import ResourceType
from toolset.gui.common.filters import NoScrollEventFilter
from toolset.gui.common.localization import translate as tr
from toolset.gui.editor import Editor

if TYPE_CHECKING:
    import os

    from pykotor.common.language import LocalizedString
    from toolset.data.installation import HTInstallation


class IFOEditor(Editor):
    """Editor for module info (IFO) files."""

    def __init__(self, parent=None, installation: HTInstallation | None = None):
        """Initialize the IFO editor."""
        supported = [ResourceType.IFO]
        super().__init__(parent, "Module Info Editor", "ifo", supported, supported, installation)

        self.ifo: IFO | None = None

        # Load UI from .ui file
        from toolset.uic.qtpy.editors.ifo import Ui_MainWindow

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self._setup_menus()
        self._add_help_action()
        self._setup_signals()

        # Setup event filter to prevent scroll wheel interaction with controls
        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

        # Setup reference search for script fields
        if installation is not None:
            self._setup_installation(installation)

        # Convert entry direction from radians (as stored) to degrees (as displayed)
        self.ui.entryDirectionSpin.setRange(0.0, 360.0)

    def _setup_signals(self):
        """Connect UI signals to handler methods."""
        # Basic info fields
        self.ui.tagGenerateButton.clicked.connect(self.generate_tag)
        for signal in (
            self.ui.tagEdit.textChanged,
            self.ui.voIdEdit.textChanged,
            self.ui.hakEdit.textChanged,
            self.ui.creatorIdSpin.valueChanged,
            self.ui.versionSpin.valueChanged,
        ):
            signal.connect(self.on_value_changed)

        # Module name and description - connect to editing finished signal
        self.ui.modNameEdit.sig_editing_finished.connect(self.on_mod_name_changed)
        self.ui.descriptionEdit.sig_editing_finished.connect(self.on_description_changed)

        # Entry point fields
        for signal in (
            self.ui.entryAreaEdit.textChanged,
            self.ui.entryXSpin.valueChanged,
            self.ui.entryYSpin.valueChanged,
            self.ui.entryZSpin.valueChanged,
        ):
            signal.connect(self.on_value_changed)
        self.ui.entryDirectionSpin.valueChanged.connect(self.on_entry_direction_changed)

        # Time settings (deprecated but still supported)
        for signal in (
            self.ui.dawnHourSpin.valueChanged,
            self.ui.duskHourSpin.valueChanged,
            self.ui.timeScaleSpin.valueChanged,
            self.ui.startMonthSpin.valueChanged,
            self.ui.startDaySpin.valueChanged,
            self.ui.startHourSpin.valueChanged,
            self.ui.startYearSpin.valueChanged,
            self.ui.xpScaleSpin.valueChanged,
        ):
            signal.connect(self.on_value_changed)

        # Script fields - map UI names to IFO attribute names
        self._script_field_mapping = {
            "onHeartbeatEdit": "on_heartbeat",
            "onLoadEdit": "on_load",
            "onStartEdit": "on_start",
            "onEnterEdit": "on_enter",
            "onLeaveEdit": "on_leave",
            "onActivateItemEdit": "on_activate_item",
            "onAcquireItemEdit": "on_acquire_item",
            "onUnacquireItemEdit": "on_unacquire_item",
            "onPlayerDeathEdit": "on_player_death",
            "onPlayerDyingEdit": "on_player_dying",
            "onPlayerLevelupEdit": "on_player_levelup",
            "onPlayerRespawnEdit": "on_player_respawn",
            "onUserDefinedEdit": "on_user_defined",
            "onPlayerRestEdit": "on_player_rest",
            "startMovieEdit": "start_movie",
        }

        for ui_name, ifo_attr in self._script_field_mapping.items():
            widget: QComboBox | QLineEdit = getattr(self.ui, ui_name)
            if hasattr(widget, "currentTextChanged"):
                widget.currentTextChanged.connect(self.on_value_changed)
            elif hasattr(widget, "textChanged"):
                widget.textChanged.connect(self.on_value_changed)

        # Advanced settings
        for signal in (
            self.ui.expansionPackSpin.valueChanged,
            self.ui.minGameVerEdit.textChanged,
            self.ui.cacheNSSDataCheck.stateChanged,
        ):
            signal.connect(self.on_value_changed)

        # Area list management (if implemented)
        self.ui.addAreaButton.clicked.connect(self.add_area)
        self.ui.removeAreaButton.clicked.connect(self.remove_area)

    def add_area(self):
        """Add an area to the module's area list."""
        # TODO: Implement area addition logic
        pass

    def remove_area(self):
        """Remove an area from the module's area list."""
        # TODO: Implement area removal logic

    def on_mod_name_changed(self):
        """Handle changes to the module name localized string."""
        if self.ifo is None:
            return
        self.ifo.mod_name = self.ui.modNameEdit.locstring()
        self.on_value_changed()

    def on_description_changed(self):
        """Handle changes to the module description localized string."""
        if self.ifo is None:
            return
        self.ifo.description = self.ui.descriptionEdit.locstring()
        self.on_value_changed()

    def _setup_installation(self, installation: HTInstallation):
        """Setup installation-specific features."""
        # Setup localized string editors
        self.ui.modNameEdit.set_installation(installation)
        self.ui.descriptionEdit.set_installation(installation)

        # Setup script field context menus and reference search
        script_fields: list[QComboBox | QLineEdit] = self._script_widgets()

        for field in script_fields:
            installation.setup_file_context_menu(
                field,
                [ResourceType.NSS, ResourceType.NCS],
                enable_reference_search=True,
                reference_search_type="script",
            )
            self._append_reference_tooltip(field, tr("Right-click to find references to this script in the installation."))
            # Set maxLength for FilterComboBox script fields (ResRefs are max 16 characters)
            line_edit: QLineEdit | None = field.lineEdit() if hasattr(field, "lineEdit") else None
            if line_edit is not None:
                line_edit.setMaxLength(16)

        # Populate script combo boxes with available scripts
        relevant_scripts: list[str] = sorted(
            iter(
                {res.resname().lower() for res in installation.get_relevant_resources(ResourceType.NCS, self._filepath)},
            ),
        )

        from toolset.gui.common.widgets.combobox import FilterComboBox

        for widget in self._script_widgets():
            if isinstance(widget, FilterComboBox):
                widget.populate_combo_box(relevant_scripts)
            elif isinstance(widget, (QComboBox,)):
                widget.clear()
                widget.addItems([""] + relevant_scripts)

    def _script_widgets(self) -> list[QComboBox | QLineEdit]:
        """Return valid script widgets from the script field mapping."""
        widgets: list[QComboBox | QLineEdit] = []
        for ui_name in self._script_field_mapping:
            widget = getattr(self.ui, ui_name, None)
            if widget is not None:
                widgets.append(widget)
        return widgets

    @staticmethod
    def _append_reference_tooltip(field: QComboBox | QLineEdit, helper_text: str) -> None:
        """Append reference-search helper text only once to an existing tooltip."""
        tooltip = field.toolTip() or ""
        if "Right-click" in tooltip:
            return
        field.setToolTip(helper_text if not tooltip else f"{tooltip}\n\n{helper_text}")

    def generate_tag(self):
        """Generate tag from module name/resref."""
        if self.ifo is None:
            return

        # Try to generate tag from module name or resref
        locstring: LocalizedString = self.ui.modNameEdit.locstring()
        if locstring and locstring.stringref != -1:
            # Try to get English text
            from pykotor.common.language import Gender, Language

            name = locstring.get(Language.ENGLISH, Gender.MALE) or ""
            if not name and self._installation:
                name = self._installation.string(locstring) or ""
            if name:
                # Generate tag from name (remove spaces, special chars)
                tag = "".join(c.lower() if c.isalnum() else "_" for c in name[:32])
                tag = tag.strip("_")
                if tag:
                    self.ui.tagEdit.setText(tag)
                    return

        # Fallback to resref
        resref = self._resname
        if resref:
            self.ui.tagEdit.setText(resref.lower())

    def on_entry_direction_changed(self):
        """Handle entry direction changes, converting degrees to radians."""
        if self.ifo is None:
            return

        # Convert degrees to radians
        degrees = self.ui.entryDirectionSpin.value()
        radians = degrees * 3.141592653589793 / 180.0
        self.ifo.entry_direction = radians
        self.on_value_changed()

    def load(
        self,
        filepath: os.PathLike | str,
        resref: str,
        restype: ResourceType,
        data: bytes | bytearray,
    ) -> None:
        """Load IFO from bytes. Defaults when field missing: Mod_ID empty, Mod_VO_ID/Mod_Tag "", Mod_Name/Mod_Entry_Area blank, Mod_Entry_X/Y/Z 0.0, Mod_On* blank, Expansion_Pack 0, Mod_Area_list optional. K1 LoadModuleStart @ 0x004c9050 (MainLoop @ 0x004babb0), TSL LoadModuleStart @ 0x0072aaa0 (MainLoop @ 0x007b6bb0)."""
        super().load(filepath, resref, restype, data)
        self.ifo = read_ifo(data)
        self.update_ui_from_ifo()

    def build(self) -> tuple[bytes, bytes]:
        """Build IFO bytes from editor state. Write values match engine read (Mod_ID, Mod_Tag, Mod_Entry_*, Mod_On*, Mod_Area_list). K1 LoadModuleStart @ 0x004c9050, TSL @ 0x0072aaa0."""
        if self.ifo is None:
            return b"", b""

        data = bytearray()
        write_gff(dismantle_ifo(self.ifo), data)
        return bytes(data), b""

    def new(self) -> None:
        """Create new IFO file."""
        super().new()
        self.ifo = IFO()
        self.update_ui_from_ifo()

    def update_ui_from_ifo(self) -> None:
        """Update UI elements from IFO data. Defaults as in construct_ifo (K1 0x004c9050, TSL 0x0072aaa0)."""
        if self.ifo is None or self._installation is None:
            return

        # Basic Info: Mod_Name/Mod_Tag/Mod_VO_ID "" or empty when missing (K1/TSL LoadModuleStart).
        self.ui.modNameEdit.set_locstring(self.ifo.mod_name)
        self.ui.tagEdit.setText(self.ifo.tag)
        self.ui.voIdEdit.setText(self.ifo.vo_id)
        self.ui.hakEdit.setText(self.ifo.hak)
        self.ui.descriptionEdit.set_locstring(self.ifo.description)

        # Module ID (read-only, display as hex)
        mod_id_str = " ".join(f"{b:02x}" for b in self.ifo.mod_id[:16]) if self.ifo.mod_id else ""
        self.ui.modIdEdit.setText(mod_id_str)

        # Creator ID and Version (deprecated)
        self.ui.creatorIdSpin.setValue(self.ifo.creator_id)
        self.ui.versionSpin.setValue(self.ifo.version)

        # Entry Point: Mod_Entry_Area blank, Mod_Entry_X/Y/Z 0.0, Mod_Entry_Dir 1,0 when missing (K1 ~174-186).
        self.ui.entryAreaEdit.setText(str(self.ifo.resref))
        self.ui.entryXSpin.setValue(self.ifo.entry_position.x)
        self.ui.entryYSpin.setValue(self.ifo.entry_position.y)
        self.ui.entryZSpin.setValue(self.ifo.entry_position.z)

        # Convert radians to degrees for display
        degrees = self.ifo.entry_direction * 180.0 / 3.141592653589793
        if degrees < 0:
            degrees += 360.0
        degrees = degrees % 360.0
        self.ui.entryDirectionSpin.setValue(degrees)

        # Area name (first area from list, read-only)
        area_name = str(self.ifo.area_name) if hasattr(self.ifo, "area_name") else ""
        self.ui.areaNameEdit.setText(area_name)

        # Time Settings (deprecated)
        self.ui.dawnHourSpin.setValue(self.ifo.dawn_hour)
        self.ui.duskHourSpin.setValue(self.ifo.dusk_hour)
        self.ui.timeScaleSpin.setValue(self.ifo.time_scale)
        self.ui.startMonthSpin.setValue(self.ifo.start_month)
        self.ui.startDaySpin.setValue(self.ifo.start_day)
        self.ui.startHourSpin.setValue(self.ifo.start_hour)
        self.ui.startYearSpin.setValue(self.ifo.start_year)
        self.ui.xpScaleSpin.setValue(self.ifo.xp_scale)

        # Scripts - update from IFO attributes to UI widgets
        for ui_name, ifo_attr in self._script_field_mapping.items():
            widget = getattr(self.ui, ui_name)
            script_value = str(getattr(self.ifo, ifo_attr))
            if isinstance(widget, QComboBox):
                widget.setCurrentText(script_value)
            elif isinstance(widget, (QLineEdit,)):
                widget.setText(script_value)

        # Advanced settings
        self.ui.expansionPackSpin.setValue(self.ifo.expansion_id)

    def on_value_changed(self) -> None:
        """Handle UI value changes. Persisted via dismantle_ifo (K1 0x004c9050, TSL 0x0072aaa0)."""
        if not self.ifo:
            return

        # Basic Info: same defaults as construct_ifo/dismantle_ifo.
        self.ifo.tag = self.ui.tagEdit.text()
        self.ifo.vo_id = self.ui.voIdEdit.text()
        self.ifo.hak = self.ui.hakEdit.text()

        # Creator ID and Version (deprecated)
        self.ifo.creator_id = self.ui.creatorIdSpin.value()
        self.ifo.version = self.ui.versionSpin.value()

        # Entry Point
        try:
            self.ifo.resref = ResRef(self.ui.entryAreaEdit.text())
        except ResRef.ExceedsMaxLengthError:
            # Skip invalid ResRef values to prevent teardown errors
            pass

        self.ifo.entry_position.x = self.ui.entryXSpin.value()
        self.ifo.entry_position.y = self.ui.entryYSpin.value()
        self.ifo.entry_position.z = self.ui.entryZSpin.value()

        # Entry direction is handled by on_entry_direction_changed (degrees to radians conversion)

        # Time Settings (deprecated)
        self.ifo.dawn_hour = self.ui.dawnHourSpin.value()
        self.ifo.dusk_hour = self.ui.duskHourSpin.value()
        self.ifo.time_scale = self.ui.timeScaleSpin.value()
        self.ifo.start_month = self.ui.startMonthSpin.value()
        self.ifo.start_day = self.ui.startDaySpin.value()
        self.ifo.start_hour = self.ui.startHourSpin.value()
        self.ifo.start_year = self.ui.startYearSpin.value()
        self.ifo.xp_scale = self.ui.xpScaleSpin.value()

        # Scripts - update from UI widgets to IFO attributes
        for ui_name, ifo_attr in self._script_field_mapping.items():
            widget = getattr(self.ui, ui_name)
            try:
                if hasattr(widget, "currentText"):
                    script_text = widget.currentText()
                elif hasattr(widget, "text"):
                    script_text = widget.text()
                else:
                    continue

                if script_text and script_text.strip():
                    setattr(self.ifo, ifo_attr, ResRef(script_text))
                else:
                    setattr(self.ifo, ifo_attr, ResRef.from_blank())
            except ResRef.ExceedsMaxLengthError:
                # Skip invalid ResRef values to prevent teardown errors
                pass

        # Advanced settings
        self.ifo.expansion_id = self.ui.expansionPackSpin.value()

        # TODO: determine if this is needed
        # self.signal_modified.emit()

if __name__ == "__main__":
    import sys

    from toolset.gui.editors.standalone import launch_editor_cli

    sys.exit(launch_editor_cli("ifo"))
