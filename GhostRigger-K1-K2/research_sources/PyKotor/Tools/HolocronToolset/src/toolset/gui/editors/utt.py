"""UTT (trigger) editor: geometry, script, and locstring fields."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

from pykotor.common.misc import ResRef
from pykotor.resource.formats.gff import write_gff
from pykotor.resource.generics.utt import UTT, dismantle_utt, read_utt
from pykotor.resource.type import ResourceType
from toolset.data.installation import HTInstallation
from toolset.gui.common.localization import translate as tr
from toolset.gui.dialogs.edit.locstring import LocalizedStringDialog
from toolset.gui.editor import Editor

if TYPE_CHECKING:
    import os

    from qtpy.QtWidgets import QWidget

    from pykotor.common.module import GFF
    from pykotor.resource.formats.twoda import TwoDA


class UTTEditor(Editor):
    def __init__(
        self,
        parent: QWidget | None,
        installation: HTInstallation | None = None,
    ):
        """Initialize the trigger editor window.

        Args:
        ----
            parent: {Parent widget}
            installation: {Installation object}.

        Processing Logic:
        ----------------
            - Initialize the base editor window
            - Set up the UI from the designer file
            - Connect menu and signal handlers
            - Load data from the provided installation if given
            - Initialize an empty UTT object.
        """
        supported = [ResourceType.UTT, ResourceType.BTT]
        super().__init__(parent, "Trigger Editor", "trigger", supported, supported, installation)

        from toolset.uic.qtpy.editors.utt import Ui_MainWindow

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self._setup_menus()
        self._add_help_action()
        self._setup_signals()
        if installation is not None:  # will only be none in the unittests
            self._setup_installation(installation)

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

        self._utt: UTT = UTT()

        self.new()

    def _setup_signals(self):
        for signal, handler in (
            (self.ui.tagGenerateButton.clicked, self.generate_tag),
            (self.ui.resrefGenerateButton.clicked, self.generate_resref),
        ):
            signal.connect(handler)

    def _script_combo_boxes(self):
        """Return all script combo boxes used by this editor."""
        return [
            self.ui.onClickEdit,
            self.ui.onDisarmEdit,
            self.ui.onEnterSelect,
            self.ui.onExitSelect,
            self.ui.onTrapTriggeredEdit,
            self.ui.onHeartbeatSelect,
            self.ui.onUserDefinedSelect,
        ]

    def _script_value_pairs(self, utt: UTT):
        """Map script combo widgets to UTT script values."""
        return [
            (self.ui.onClickEdit, utt.on_click),
            (self.ui.onDisarmEdit, utt.on_disarm),
            (self.ui.onEnterSelect, utt.on_enter),
            (self.ui.onExitSelect, utt.on_exit),
            (self.ui.onHeartbeatSelect, utt.on_heartbeat),
            (self.ui.onTrapTriggeredEdit, utt.on_trap_triggered),
            (self.ui.onUserDefinedSelect, utt.on_user_defined),
        ]

    def _setup_reference_field(
        self,
        widget,
        resource_types: list[ResourceType],
        reference_type: str,
        tooltip_text: str,
        *,
        set_max_length: bool = False,
    ) -> None:
        """Configure context-menu reference search behavior for a widget."""
        assert self._installation is not None
        self._installation.setup_file_context_menu(
            widget,
            resource_types,
            enable_reference_search=True,
            reference_search_type=reference_type,
        )
        widget.setToolTip(tr(tooltip_text))

        if set_max_length and hasattr(widget, "lineEdit"):
            line_edit = widget.lineEdit()
            if line_edit is not None:
                line_edit.setMaxLength(16)

    def _setup_installation(
        self,
        installation: HTInstallation,
    ):
        self._installation = installation
        self.ui.nameEdit.set_installation(installation)

        cursors: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_CURSORS)
        factions: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_FACTIONS)
        traps: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_TRAPS)

        for widget, twoda, twoda_name in (
            (self.ui.cursorSelect, cursors, HTInstallation.TwoDA_CURSORS),
            (self.ui.factionSelect, factions, HTInstallation.TwoDA_FACTIONS),
            (self.ui.trapSelect, traps, HTInstallation.TwoDA_TRAPS),
        ):
            if twoda:
                widget.set_context(twoda, installation, twoda_name)
                widget.set_items(twoda.get_column("label"))

        self.relevant_script_resnames: list[str] = sorted(iter({res.resname().lower() for res in self._installation.get_relevant_resources(ResourceType.NCS, self._filepath)}))

        for combo_box in self._script_combo_boxes():
            combo_box.populate_combo_box(self.relevant_script_resnames)
            self._setup_reference_field(
                combo_box,
                [ResourceType.NCS, ResourceType.NSS],
                "script",
                "Right-click to find references to this script in the installation.",
                set_max_length=True,
            )

        # Setup reference search for Tag field
        self._setup_reference_field(self.ui.tagEdit, [], "tag", "Right-click to find references to this tag in the installation.")

        # Setup reference search for TemplateResRef field
        self._setup_reference_field(
            self.ui.resrefEdit,
            [],
            "template_resref",
            "Right-click to find references to this template resref in the installation.",
        )

    def load(
        self,
        filepath: os.PathLike | str,
        resref: str,
        restype: ResourceType,
        data: bytes,
    ):
        """Load resource and populate UI from UTT. Defaults from construct_utt (K1 LoadTrigger 0x0058da80; TSL TODO)."""
        super().load(filepath, resref, restype, data)

        utt: UTT = read_utt(data)
        self._loadUTT(utt)

    def _loadUTT(
        self,
        utt: UTT,
    ):
        """Loads UTT data into UI elements.

        Args:
        ----
            utt: UTT - UTT object to load data from

        Defaults from construct_utt; K1 LoadTrigger 0x0058da80; TSL same (addresses TODO). Sets name, tag, resref, cursor, type, trap, scripts, comment.
        """
        self._utt = utt

        # Basic
        self.ui.nameEdit.set_locstring(utt.name)
        self.ui.tagEdit.setText(utt.tag)
        self.ui.resrefEdit.setText(str(utt.resref))
        self.ui.cursorSelect.setCurrentIndex(utt.cursor_id)
        self.ui.typeSelect.setCurrentIndex(utt.type_id)

        # Advanced
        self.ui.autoRemoveKeyCheckbox.setChecked(utt.auto_remove_key)
        self.ui.keyEdit.setText(utt.key_name)
        self.ui.factionSelect.setCurrentIndex(utt.faction_id)
        self.ui.highlightHeightSpin.setValue(utt.highlight_height)

        # Trap
        self.ui.isTrapCheckbox.setChecked(utt.is_trap)
        self.ui.activateOnceCheckbox.setChecked(utt.trap_once)
        self.ui.detectableCheckbox.setChecked(utt.trap_detectable)
        self.ui.detectDcSpin.setValue(utt.trap_detect_dc)
        self.ui.disarmableCheckbox.setChecked(utt.trap_disarmable)
        self.ui.disarmDcSpin.setValue(utt.trap_disarm_dc)
        self.ui.trapSelect.setCurrentIndex(utt.trap_type)

        # Scripts
        for combo_box, value in self._script_value_pairs(utt):
            combo_box.set_combo_box_text(str(value))

        # Comments
        self.ui.commentsEdit.setPlainText(utt.comment)

    def build(self) -> tuple[bytes, bytes]:
        """Builds a UTT from UI data.

        Returns:
        -------
            tuple[bytes, bytes]: GFF data and log.

        Populates UTT from UI, then dismantle_utt (K1 LoadTrigger 0x0058da80; TSL TODO). Returns GFF bytes and log.
        """
        utt: UTT = deepcopy(self._utt)

        # Basic
        utt.name = self.ui.nameEdit.locstring()
        utt.tag = self.ui.tagEdit.text()
        utt.resref = ResRef(self.ui.resrefEdit.text())
        utt.cursor_id = self.ui.cursorSelect.currentIndex()
        utt.type_id = self.ui.typeSelect.currentIndex()

        # Advanced
        utt.auto_remove_key = self.ui.autoRemoveKeyCheckbox.isChecked()
        utt.key_name = self.ui.keyEdit.text()
        utt.faction_id = self.ui.factionSelect.currentIndex()
        utt.highlight_height = self.ui.highlightHeightSpin.value()

        # Trap
        utt.is_trap = self.ui.isTrapCheckbox.isChecked()
        utt.trap_once = self.ui.activateOnceCheckbox.isChecked()
        utt.trap_detectable = self.ui.detectableCheckbox.isChecked()
        utt.trap_detect_dc = self.ui.detectDcSpin.value()
        utt.trap_disarmable = self.ui.disarmableCheckbox.isChecked()
        utt.trap_disarm_dc = self.ui.disarmDcSpin.value()
        utt.trap_type = self.ui.trapSelect.currentIndex()

        # Scripts
        for attr_name, combo_box in (
            ("on_click", self.ui.onClickEdit),
            ("on_disarm", self.ui.onDisarmEdit),
            ("on_enter", self.ui.onEnterSelect),
            ("on_exit", self.ui.onExitSelect),
            ("on_heartbeat", self.ui.onHeartbeatSelect),
            ("on_trap_triggered", self.ui.onTrapTriggeredEdit),
            ("on_user_defined", self.ui.onUserDefinedSelect),
        ):
            setattr(utt, attr_name, ResRef(combo_box.currentText()))

        # Comments
        utt.comment = self.ui.commentsEdit.toPlainText()

        data = bytearray()
        gff: GFF = dismantle_utt(utt)
        write_gff(gff, data)

        return data, b""

    def new(self):
        super().new()
        self._loadUTT(UTT())

    def change_name(self):
        assert self._installation is not None
        dialog = LocalizedStringDialog(self, self._installation, self.ui.nameEdit.locstring())
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
            self.ui.resrefEdit.setText("m00xx_trg_000")

if __name__ == "__main__":
    import sys

    from toolset.gui.editors.standalone import launch_editor_cli

    sys.exit(launch_editor_cli("utt"))
