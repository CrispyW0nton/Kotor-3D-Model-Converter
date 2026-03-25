"""UTE (encounter) editor: creature list, spawn points, and difficulty."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, cast

from qtpy.QtWidgets import QCheckBox, QDoubleSpinBox, QSizePolicy, QSpinBox

from pykotor.common.misc import ResRef
from pykotor.resource.formats.gff import write_gff
from pykotor.resource.generics.ute import UTE, UTECreature, dismantle_ute, read_ute
from pykotor.resource.type import ResourceType
from toolset.data.installation import HTInstallation
from toolset.gui.common.widgets.combobox import FilterComboBox
from toolset.gui.dialogs.edit.locstring import LocalizedStringDialog
from toolset.gui.editor import Editor

if TYPE_CHECKING:
    import os

    from qtpy.QtWidgets import QWidget

    from pykotor.resource.formats.gff.gff_data import GFF
    from pykotor.resource.formats.twoda.twoda_data import TwoDA


class UTEEditor(Editor):
    def __init__(
        self,
        parent: QWidget | None,
        installation: HTInstallation | None = None,
    ):
        """Initialize the trigger editor window.

        Args:
        ----
            parent: {The parent widget of the editor}
            installation: {The installation object being edited}.

        Processing Logic:
        ----------------
            - Call super().__init__ to initialize base editor class
            - Load UI from designer file
            - Set up menus, signals and installation
            - Initialize UTE object
            - Call new() to start with a blank trigger.
        """
        supported: list[ResourceType] = [ResourceType.UTE, ResourceType.BTE]
        super().__init__(parent, "Trigger Editor", "trigger", supported, supported, installation)

        from toolset.uic.qtpy.editors.ute import Ui_MainWindow

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self._setup_menus()
        self._add_help_action()
        self._setup_signals()
        if installation is not None:  # will only be none in the unittests
            self._setup_installation(installation)

        self._ute: UTE = UTE()

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

        self.new()

    def _on_installation_changed(self, installation: HTInstallation | None) -> None:
        if installation is None:
            return
        self._setup_installation(installation)

    def _setup_signals(self):
        """Connects UI signals to handler functions.

        Processing Logic:
        ----------------
            - Connects the tagGenerateButton clicked signal to generate_tag handler
            - Connects the resrefGenerateButton clicked signal to generate_resref handler
            - Connects the infiniteRespawnCheckbox stateChanged signal to setInfiniteRespawn handler
            - Connects the spawnSelect currentIndexChanged signal to setContinuous handler
            - Connects the addCreatureButton clicked signal to addCreature handler
            - Connects the removeCreatureButton clicked signal to remove_selectedCreature handler.
        """
        signal_connections = [
            (self.ui.tagGenerateButton.clicked, self.generate_tag),
            (self.ui.resrefGenerateButton.clicked, self.generate_resref),
            (self.ui.infiniteRespawnCheckbox.stateChanged, self.set_infinite_respawn),
            (self.ui.spawnSelect.currentIndexChanged, self.set_continuous),
            (self.ui.addCreatureButton.clicked, self.add_creature),
            (self.ui.removeCreatureButton.clicked, self.remove_selected_creature),
        ]
        for signal, handler in signal_connections:
            signal.connect(handler)

    def _script_combo_boxes(self) -> list[FilterComboBox]:
        """Return all script combo boxes used by this editor."""
        return [
            self.ui.onEnterSelect,
            self.ui.onExitSelect,
            self.ui.onExhaustedEdit,
            self.ui.onHeartbeatSelect,
            self.ui.onUserDefinedSelect,
        ]

    def _script_value_pairs(self, ute: UTE) -> list[tuple[FilterComboBox, ResRef]]:
        """Map script combo boxes to UTE script values."""
        return [
            (self.ui.onEnterSelect, ute.on_entered),
            (self.ui.onExitSelect, ute.on_exit),
            (self.ui.onExhaustedEdit, ute.on_exhausted),
            (self.ui.onHeartbeatSelect, ute.on_heartbeat),
            (self.ui.onUserDefinedSelect, ute.on_user_defined),
        ]

    def _setup_script_reference_field(self, combo_box: FilterComboBox) -> None:
        """Configure script combo reference search behavior and length limits."""
        assert self._installation is not None
        self._installation.setup_file_context_menu(combo_box, [ResourceType.NSS, ResourceType.NCS])
        line_edit = combo_box.lineEdit()
        if line_edit is not None:
            line_edit.setMaxLength(16)

    def _setup_installation(
        self,
        installation: HTInstallation,
    ):
        """Sets up the installation details in the UI.

        Args:
        ----
            installation: {The installation object being edited}

        Processing Logic:
        ----------------
            - Sets the internal installation object reference
            - Populates the name field with the installation details
            - Fetches the faction and difficulty data from the installation
            - Clears and populates the dropdowns with the faction and difficulty labels
        """
        self._installation = installation
        self.ui.nameEdit.set_installation(installation)

        difficulties: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_ENC_DIFFICULTIES)
        self.ui.difficultySelect.clear()
        if difficulties is not None:
            self.ui.difficultySelect.set_items(difficulties.get_column("label"))
        self.ui.difficultySelect.set_context(difficulties, installation, HTInstallation.TwoDA_ENC_DIFFICULTIES)

        factions: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_FACTIONS)
        self.ui.factionSelect.clear()
        if factions is not None:
            self.ui.factionSelect.set_items(factions.get_column("label"))
        self.ui.factionSelect.set_context(factions, installation, HTInstallation.TwoDA_FACTIONS)

        for combo_box in self._script_combo_boxes():
            self._setup_script_reference_field(combo_box)
        self.relevant_creature_resnames = sorted(iter({res.resname().lower() for res in self._installation.get_relevant_resources(ResourceType.UTC, self._filepath)}))

    def load(
        self,
        filepath: os.PathLike | str,
        resref: str,
        restype: ResourceType,
        data: bytes,
    ):
        """Load resource and populate UI from UTE. Defaults from construct_ute (K1 LoadEncounter 0x00593830, TSL 0x007eb810)."""
        super().load(filepath, resref, restype, data)

        ute: UTE = read_ute(data)
        self._loadUTE(ute)

    def _loadUTE(self, ute: UTE):
        """Loads UTE data into UI elements.

        Args:
        ----
            ute (UTE): UTE object to load

        Defaults from construct_ute; K1 LoadEncounter 0x00593830, TSL ReadEncounterFromGff 0x007eb810. Sets Basic, Advanced, creatures, scripts, comment.
        """
        self._ute = ute

        # Basic
        self.ui.nameEdit.set_locstring(ute.name)
        self.ui.tagEdit.setText(ute.tag)
        self.ui.resrefEdit.setText(str(ute.resref))
        self.ui.difficultySelect.setCurrentIndex(ute.difficulty_id)
        self.ui.spawnSelect.setCurrentIndex(int(ute.single_shot))
        self.ui.minCreatureSpin.setValue(ute.rec_creatures)
        self.ui.maxCreatureSpin.setValue(ute.max_creatures)

        # Advanced
        self.ui.activeCheckbox.setChecked(ute.active)
        self.ui.playerOnlyCheckbox.setChecked(ute.player_only)
        self.ui.factionSelect.setCurrentIndex(ute.faction_id)
        self.ui.respawnsCheckbox.setChecked(ute.reset)
        self.ui.infiniteRespawnCheckbox.setChecked(ute.respawns == -1)
        self.ui.respawnTimeSpin.setValue(ute.reset_time)
        self.ui.respawnCountSpin.setValue(ute.respawns)

        # Creatures
        self.ui.creatureTable.setRowCount(0)
        for creature in ute.creatures:
            self.add_creature(
                resname=str(creature.resref),
                appearance_id=creature.appearance_id,
                challenge=creature.challenge_rating,
                single=creature.single_spawn,
            )

        # Scripts
        for combo_box, value in self._script_value_pairs(ute):
            combo_box.set_combo_box_text(str(value))

        self.relevant_script_resnames = sorted(iter({res.resname().lower() for res in self._installation.get_relevant_resources(ResourceType.NCS, self._filepath)}))

        for combo_box in self._script_combo_boxes():
            combo_box.populate_combo_box(self.relevant_script_resnames)

        # Comments
        self.ui.commentsEdit.setPlainText(ute.comment)

    def build(self) -> tuple[bytes, bytes]:
        """Builds a UTE from UI data.

        Returns:
        -------
            tuple[bytes, bytes]: UTE GFF data and log.

        Populates UTE from UI, then dismantle_ute (K1 SaveEncounter 0x00591350, TSL 0x007ed770). Returns GFF bytes and log.
        """
        ute: UTE = deepcopy(self._ute)

        # Basic
        ute.name = self.ui.nameEdit.locstring()
        ute.tag = self.ui.tagEdit.text()
        ute.resref = ResRef(self.ui.resrefEdit.text())
        ute.difficulty_id = self.ui.difficultySelect.currentIndex()
        ute.single_shot = bool(self.ui.spawnSelect.currentIndex())
        ute.rec_creatures = self.ui.minCreatureSpin.value()
        ute.max_creatures = self.ui.maxCreatureSpin.value()

        # Advanced
        ute.active = self.ui.activeCheckbox.isChecked()
        ute.player_only = self.ui.playerOnlyCheckbox.isChecked()
        ute.faction_id = self.ui.factionSelect.currentIndex()
        ute.reset = self.ui.respawnsCheckbox.isChecked()
        ute.respawns = self.ui.respawnCountSpin.value()
        ute.reset_time = self.ui.respawnTimeSpin.value()

        # Creatures
        ute.creatures = []
        for i in range(self.ui.creatureTable.rowCount()):
            singleCheckbox = cast("QCheckBox", self.ui.creatureTable.cellWidget(i, 0))
            challengeSpin = cast("QDoubleSpinBox", self.ui.creatureTable.cellWidget(i, 1))
            appearanceSpin = cast("QSpinBox", self.ui.creatureTable.cellWidget(i, 2))
            resrefCombo = cast("FilterComboBox", self.ui.creatureTable.cellWidget(i, 3))

            if resrefCombo is None:
                continue  # Skip rows without a resref combo widget

            creature = UTECreature()
            creature.resref = ResRef(resrefCombo.currentText())
            creature.single_spawn = singleCheckbox.isChecked()
            creature.appearance_id = appearanceSpin.value()
            creature.challenge_rating = challengeSpin.value()
            ute.creatures.append(creature)

        # Scripts
        for attr_name, combo_box in (
            ("on_entered", self.ui.onEnterSelect),
            ("on_exit", self.ui.onExitSelect),
            ("on_exhausted", self.ui.onExhaustedEdit),
            ("on_heartbeat", self.ui.onHeartbeatSelect),
            ("on_user_defined", self.ui.onUserDefinedSelect),
        ):
            setattr(ute, attr_name, ResRef(combo_box.currentText()))

        # Comments
        ute.comment = self.ui.commentsEdit.toPlainText()

        data = bytearray()
        gff: GFF = dismantle_ute(ute)
        write_gff(gff, data)

        return data, b""

    def new(self):
        super().new()
        self._loadUTE(UTE())

    def change_name(self):
        dialog: LocalizedStringDialog = LocalizedStringDialog(self, self._installation, self.ui.nameEdit.locstring())
        if dialog.exec():
            self._load_locstring(self.ui.nameEdit.ui.locstringText, dialog.locstring)

    def generate_tag(self):
        if not self.ui.resrefEdit.text():
            self.generate_resref()
        self.ui.tagEdit.setText(self.ui.resrefEdit.text())

    def generate_resref(self):
        if self._resname:
            self.ui.resrefEdit.setText(self._resname)
        else:
            self.ui.resrefEdit.setText("m00xx_enc_000")

    def set_infinite_respawn(self):
        if self.ui.infiniteRespawnCheckbox.isChecked():
            self._set_infinite_respawn_main(val=-1, enabled=False)
        else:
            self._set_infinite_respawn_main(val=0, enabled=True)

    def _set_infinite_respawn_main(
        self,
        val: int,
        *,
        enabled: bool,
    ):
        self.ui.respawnCountSpin.setMinimum(val)
        self.ui.respawnCountSpin.setValue(val)
        self.ui.respawnCountSpin.setEnabled(enabled)

    def set_continuous(self, *args, **kwargs):
        is_continuous: bool = self.ui.spawnSelect.currentIndex() == 1
        self.ui.respawnsCheckbox.setEnabled(is_continuous)
        self.ui.infiniteRespawnCheckbox.setEnabled(is_continuous)
        self.ui.respawnCountSpin.setEnabled(is_continuous)
        self.ui.respawnTimeSpin.setEnabled(is_continuous)

    def add_creature(
        self,
        *args,
        resname: str = "",
        appearance_id: int = 0,
        challenge: float = 0.0,
        single: bool = False,
    ):
        """Adds a new creature to the creature table.

        Args:
        ----
            resname (str): Name of the creature
            appearance_id (int): ID number for the creature's appearance
            challenge (float): Difficulty rating for the creature
            single (bool): Whether the creature is a single creature encounter

        Processing Logic:
        ----------------
            - Gets the current row count of the creature table
            - Inserts a new row at that index
            - Creates widgets for the single checkbox, challenge spinbox, and appearance spinbox
            - Sets the values of the widgets based on function arguments
            - Sets the widgets as the cell widgets in the appropriate columns
            - Sets the creature name as the item in the name column.
        """
        row_id: int = self.ui.creatureTable.rowCount()
        self.ui.creatureTable.insertRow(row_id)

        single_checkbox = QCheckBox()
        single_checkbox.setChecked(single)
        challenge_spin = QDoubleSpinBox()
        challenge_spin.setValue(challenge)
        appearance_spin = QSpinBox()
        appearance_spin.setValue(appearance_id)
        resref_combo = FilterComboBox()
        resref_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        resref_combo.setMinimumWidth(20)
        resref_combo.populate_combo_box(self.relevant_creature_resnames)
        resref_combo.set_combo_box_text(resname)
        if self._installation is not None:
            self._installation.setup_file_context_menu(resref_combo, [ResourceType.UTC])

        self.ui.creatureTable.setCellWidget(row_id, 0, single_checkbox)
        self.ui.creatureTable.setCellWidget(row_id, 1, challenge_spin)
        self.ui.creatureTable.setCellWidget(row_id, 2, appearance_spin)
        self.ui.creatureTable.setCellWidget(row_id, 3, resref_combo)

    def remove_selected_creature(self):
        # Try selection model first (works when cells have items)
        sel_model = self.ui.creatureTable.selectionModel()
        if sel_model is not None:
            indices = sel_model.selectedRows()
            if indices:
                # Remove rows in reverse order to maintain correct indices
                for index in sorted(indices, reverse=True):
                    self.ui.creatureTable.removeRow(index.row())
                return

        # Fallback to currentRow (works when cells have widgets)
        current_row = self.ui.creatureTable.currentRow()
        if current_row >= 0:
            self.ui.creatureTable.removeRow(current_row)

if __name__ == "__main__":
    import sys

    from toolset.gui.editors.standalone import launch_editor_cli

    sys.exit(launch_editor_cli("ute"))
