"""UTW (waypoint) editor: locstring name and linked module waypoint."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

from loggerplus import RobustLogger
from pykotor.common.language import LocalizedString
from pykotor.common.misc import ResRef
from pykotor.resource.formats.gff import write_gff
from pykotor.resource.generics.utw import UTW, dismantle_utw, read_utw
from pykotor.resource.type import ResourceType
from toolset.gui.common.localization import trf
from toolset.gui.dialogs.edit.locstring import LocalizedStringDialog
from toolset.gui.editor import Editor

if TYPE_CHECKING:
    import os

    from qtpy.QtWidgets import QWidget

    from pykotor.common.module import GFF
    from toolset.data.installation import HTInstallation


class UTWEditor(Editor):
    def __init__(
        self,
        parent: QWidget | None,
        installation: HTInstallation | None = None,
    ):
        """Initialize Waypoint Editor window.

        Args:
        ----
            parent: {Parent widget}
            installation: {Installation object}.

        Processing Logic:
        ----------------
            - Initialize UI elements from designer file
            - Set up menu bar and signal connections
            - Load installation data if provided
            - Initialize UTW object
            - Create new empty waypoint by default.
        """
        supported: list[ResourceType] = [ResourceType.UTW]
        super().__init__(parent, "Waypoint Editor", "waypoint", supported, supported, installation)

        from toolset.uic.qtpy.editors.utw import Ui_MainWindow

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

        self._utw = UTW()

        self.new()

    def _setup_signals(self):
        for signal, handler in (
            (self.ui.tagGenerateButton.clicked, self.generate_tag),
            (self.ui.resrefGenerateButton.clicked, self.generate_resref),
            (self.ui.noteChangeButton.clicked, self.change_note),
        ):
            signal.connect(handler)

    def _setup_installation(self, installation: HTInstallation):
        self._installation = installation
        self.ui.nameEdit.set_installation(installation)

    def _set_map_note_locstring(self, locstring: LocalizedString):
        self._load_locstring(self.ui.noteEdit, locstring)

    def _get_map_note_locstring(self) -> LocalizedString:
        return self.ui.noteEdit.locstring()

    def _load_basic_fields(self, utw: UTW):
        self.ui.nameEdit.set_locstring(utw.name)
        self.ui.tagEdit.setText(utw.tag)
        self.ui.resrefEdit.setText(str(utw.resref))

    def _save_basic_fields(self, utw: UTW):
        utw.name = self.ui.nameEdit.locstring()
        utw.tag = self.ui.tagEdit.text()
        utw.resref = ResRef(self.ui.resrefEdit.text())

    def load(
        self,
        filepath: os.PathLike | str,
        resref: str,
        restype: ResourceType,
        data: bytes,
    ):
        """Load resource and populate UI from UTW. Defaults from construct_utw (K1 LoadWaypoint 0x005c7f30; TSL TODO)."""
        super().load(filepath, resref, restype, data)

        utw: UTW = read_utw(data)
        self._loadUTW(utw)

    def _loadUTW(self, utw: UTW):
        """Load UTW data into UI elements.

        Args:
        ----
            utw (UTW): UTW object to load data from

        Defaults from construct_utw; K1 LoadWaypoint 0x005c7f30; TSL same (addresses TODO). Sets name, tag, resref, map note, comment.
        """
        self._utw: UTW = utw

        # Basic (Tag "", LocalizedName empty, TemplateResRef blank per K1)
        self._load_basic_fields(utw)

        # Advanced (HasMapNote 0, MapNoteEnabled 0, MapNote empty per K1 LoadWaypoint)
        self.ui.isNoteCheckbox.setChecked(utw.has_map_note)
        self.ui.noteEnabledCheckbox.setChecked(utw.map_note_enabled)
        self._set_map_note_locstring(utw.map_note)

        # Comments (toolset-only; default "")
        self.ui.commentsEdit.setPlainText(utw.comment)

    def build(self) -> tuple[bytes, bytes]:
        """Builds a UTW from UI data.

        Returns:
        -------
            tuple[bytes, bytes]: GFF data and log.

        Populates UTW from UI, then dismantle_utw (K1 LoadWaypoint 0x005c7f30; TSL TODO). Returns GFF bytes and log.
        """
        utw: UTW = deepcopy(self._utw)

        self._save_basic_fields(utw)
        utw.has_map_note = self.ui.isNoteCheckbox.isChecked()
        utw.map_note_enabled = self.ui.noteEnabledCheckbox.isChecked()
        utw.map_note = self._get_map_note_locstring()
        utw.comment = self.ui.commentsEdit.toPlainText()

        data = bytearray()
        gff: GFF = dismantle_utw(utw)
        write_gff(gff, data)

        return bytes(data), b""

    def new(self):
        super().new()
        self._loadUTW(UTW())

    def _edit_locstring(self, current: LocalizedString, apply_func) -> None:
        """Open a localized string dialog and apply result when accepted."""
        assert self._installation is not None
        dialog = LocalizedStringDialog(self, self._installation, current)
        if dialog.exec():
            apply_func(dialog.locstring)

    def change_name(self):
        self._edit_locstring(
            self.ui.nameEdit.locstring(),
            lambda locstring: self._load_locstring(self.ui.nameEdit.ui.locstringText, locstring),  # pyright: ignore[reportArgumentType]
        )

    def change_note(self):
        self._edit_locstring(self._get_map_note_locstring(), self._set_map_note_locstring)

    def generate_tag(self):
        resref_edit_text = self.ui.resrefEdit.text()
        if not resref_edit_text or not resref_edit_text.strip():
            self.generate_resref()
            resref_edit_text = self.ui.resrefEdit.text()
        self.ui.tagEdit.setText(resref_edit_text)

    def generate_resref(self):
        if self._resname:
            self.ui.resrefEdit.setText(self._resname)
        else:
            self.ui.resrefEdit.setText("m00xx_way_000")

if __name__ == "__main__":
    import sys

    from toolset.gui.editors.standalone import launch_editor_cli

    sys.exit(launch_editor_cli("utw"))
