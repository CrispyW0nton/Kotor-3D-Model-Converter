"""Comprehensive TSLPatchData editor for creating HoloPatcher/TSLPatcher mods."""

from __future__ import annotations

import configparser

from pathlib import Path
from typing import TYPE_CHECKING

from qtpy.QtWidgets import (
    QDialog,
    QFileDialog,
    QMessageBox,
    QTreeWidgetItem,
)

if TYPE_CHECKING:
    from qtpy.QtWidgets import (
        QWidget,
    )

    from toolset.data.installation import HTInstallation


class TSLPatchDataEditor(QDialog):
    """Comprehensive editor for TSLPatchData configuration."""

    def __init__(
        self,
        parent: QWidget | None,
        installation: HTInstallation | None = None,
        tslpatchdata_path: Path | None = None,
    ):
        super().__init__(parent)
        from toolset.gui.common.localization import translate as tr

        self.setWindowTitle(tr("TSLPatchData Editor - Create HoloPatcher Mod"))
        self.resize(1400, 900)

        self.installation = installation
        self.tslpatchdata_path = tslpatchdata_path or Path("tslpatchdata")
        self.ini_config = configparser.ConfigParser(delimiters=("="), allow_no_value=True, strict=False, interpolation=None, inline_comment_prefixes=(";", "#"))

        self._setup_ui()

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

        if tslpatchdata_path and tslpatchdata_path.exists():
            self._load_existing_config()

    def _setup_ui(self):
        """Set up the user interface."""
        from toolset.gui.common.localization import translate as tr
        from toolset.uic.qtpy.dialogs.tslpatchdata_editor import Ui_Dialog

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        # Set initial path
        self.ui.pathEdit.setText(str(self.tslpatchdata_path))

        # Set header labels with translation
        self.ui.pathLabel.setText(tr("<b>TSLPatchData Folder:</b>"))
        self.ui.filesLabel.setText(tr("<b>Files to Package:</b>"))
        self.ui.fileTree.setHeaderLabels([tr("File"), tr("Type"), tr("Status")])

        # Set splitter stretch factors
        self.ui.mainSplitter.setStretchFactor(0, 1)
        self.ui.mainSplitter.setStretchFactor(1, 2)

        # Connect signals
        self.ui.browseBtn.clicked.connect(self._browse_tslpatchdata_path)
        self.ui.createBtn.clicked.connect(self._create_new_tslpatchdata)
        self.ui.fileTree.itemClicked.connect(self._on_file_selected)
        self.ui.addFileBtn.clicked.connect(self._add_file)
        self.ui.removeFileBtn.clicked.connect(self._remove_file)
        self.ui.scanDiffBtn.clicked.connect(self._scan_from_diff)

        # 2DA Memory tab signals
        self.ui.twodaList.itemClicked.connect(self._on_2da_selected)
        self.ui.add2daBtn.clicked.connect(self._add_2da_memory)
        self.ui.addTokenBtn.clicked.connect(self._add_2da_token)
        self.ui.editTokenBtn.clicked.connect(self._edit_2da_token)
        self.ui.removeTokenBtn.clicked.connect(self._remove_2da_token)

        # TLK StrRef tab signals
        self.ui.addTlkStrBtn.clicked.connect(self._add_tlk_string)
        self.ui.editTlkStrBtn.clicked.connect(self._edit_tlk_string)
        self.ui.removeTlkStrBtn.clicked.connect(self._remove_tlk_string)
        self.ui.openTlkEditorBtn.clicked.connect(self._open_tlk_editor)

        # GFF Fields tab signals
        self.ui.gffFileList.itemClicked.connect(self._on_gff_file_selected)
        self.ui.openGffEditorBtn.clicked.connect(self._open_gff_editor)

        # Scripts tab signals
        self.ui.addScriptBtn.clicked.connect(self._add_script)
        self.ui.removeScriptBtn.clicked.connect(self._remove_script)

        # INI Preview tab signals
        self.ui.refreshPreviewBtn.clicked.connect(self._update_ini_preview)
        self.ui.iniPreviewText.setFont(self.font())

        # Bottom button signals
        self.ui.generateBtn.clicked.connect(self._generate_tslpatchdata)
        self.ui.previewBtn.clicked.connect(self._preview_ini)
        self.ui.saveBtn.clicked.connect(self._save_configuration)
        self.ui.closeBtn.clicked.connect(lambda: self.accept())

    # Implementation methods
    def _browse_tslpatchdata_path(self):
        """Browse for tslpatchdata folder."""
        path = QFileDialog.getExistingDirectory(self, "Select TSLPatchData Folder")
        if path:
            self.tslpatchdata_path = Path(path)
            self.ui.pathEdit.setText(str(self.tslpatchdata_path))
            self._load_existing_config()

    def _create_new_tslpatchdata(self):
        """Create a new tslpatchdata folder structure."""
        path = QFileDialog.getExistingDirectory(self, "Select Location for New TSLPatchData")
        if not path:
            return

        self.tslpatchdata_path = Path(path) / "tslpatchdata"
        self.tslpatchdata_path.mkdir(exist_ok=True)
        self.ui.pathEdit.setText(str(self.tslpatchdata_path))

        from toolset.gui.common.localization import translate as tr, trf

        QMessageBox.information(
            self,
            tr("Created"),
            trf("New tslpatchdata folder created at:\n{path}", path=str(self.tslpatchdata_path)),
        )

    def _load_existing_config(self):
        """Load existing TSLPatchData configuration."""
        ini_path = self.tslpatchdata_path / "changes.ini"
        if not ini_path.exists():
            return

        self.ini_config.read(ini_path)
        # TODO: Parse and populate UI from ini_config
        self._update_ini_preview()

    def _add_file(self):
        """Add a file to the package."""
        from toolset.gui.common.localization import translate as tr

        files = QFileDialog.getOpenFileNames(self, tr("Select Files to Add"))[0]
        for file_path in files:
            from toolset.gui.common.localization import translate as tr

            item = QTreeWidgetItem([Path(file_path).name, tr("Added"), tr("New")])
            self.ui.fileTree.addTopLevelItem(item)

    def _remove_file(self):
        """Remove selected file from package."""
        current = self.ui.fileTree.currentItem()
        if current:
            self.ui.fileTree.takeTopLevelItem(self.ui.fileTree.indexOfTopLevelItem(current))

    def _scan_from_diff(self):
        """Scan files from KotorDiff results."""
        from toolset.gui.common.localization import translate as tr

        QMessageBox.information(
            self,
            tr("Scan from Diff"),
            tr("This will scan a KotorDiff results file and automatically populate files.\n\nNot yet implemented."),
        )

    def _on_file_selected(self, item):
        """Handle file selection in tree."""
        # TODO: Update details based on selected file

    def _add_2da_memory(self):
        """Add a new 2DA memory tracking entry."""
        # TODO: Show dialog to add 2DA

    def _on_2da_selected(self, item):
        """Handle 2DA file selection."""
        # TODO: Load and display tokens for selected 2DA

    def _add_2da_token(self):
        """Add a memory token for the selected 2DA."""
        # TODO: Show dialog to add token

    def _edit_2da_token(self):
        """Edit selected memory token."""
        # TODO: Show edit dialog

    def _remove_2da_token(self):
        """Remove selected memory token."""
        current = self.ui.twodaTokensTree.currentItem()
        if current:
            index = self.ui.twodaTokensTree.indexOfTopLevelItem(current)
            self.ui.twodaTokensTree.takeTopLevelItem(index)

    def _add_tlk_string(self):
        """Add a TLK string reference."""
        # TODO: Show dialog to add string

    def _edit_tlk_string(self):
        """Edit selected TLK string."""
        # TODO: Show edit dialog

    def _remove_tlk_string(self):
        """Remove selected TLK string."""
        current = self.ui.tlkStringTree.currentItem()
        if current:
            index = self.ui.tlkStringTree.indexOfTopLevelItem(current)
            self.ui.tlkStringTree.takeTopLevelItem(index)

    def _open_tlk_editor(self):
        """Open the TLK editor for the installation."""
        if self.installation:
            from pykotor.common.stream import BinaryReader
            from pykotor.resource.type import ResourceType
            from toolset.utils.window import openResourceEditor

            tlk_path = self.installation.path() / "dialog.tlk"
            if tlk_path.is_file():
                openResourceEditor(
                    tlk_path,
                    "dialog",
                    ResourceType.TLK,
                    BinaryReader.load_file(tlk_path),
                    self.installation,
                    self,
                )
            else:
                from toolset.gui.common.localization import translate as tr

                QMessageBox.warning(self, tr("Not Found"), tr("dialog.tlk not found in installation."))
        else:
            QMessageBox.warning(self, tr("No Installation"), tr("No installation loaded."))

    def _on_gff_file_selected(self, item):
        """Handle GFF file selection."""
        # TODO: Load and display field modifications

    def _open_gff_editor(self):
        """Open GFF editor for selected file."""
        # TODO: Open selected GFF in editor

    def _add_script(self):
        """Add a compiled script."""
        from toolset.gui.common.localization import translate as tr

        files = QFileDialog.getOpenFileNames(self, tr("Select Scripts (.ncs)"), "", "Scripts (*.ncs)")[0]
        for file_path in files:
            self.ui.scriptList.addItem(Path(file_path).name)

    def _remove_script(self):
        """Remove selected script."""
        current = self.ui.scriptList.currentItem()
        if current:
            self.ui.scriptList.takeItem(self.ui.scriptList.row(current))

    def _update_ini_preview(self):
        """Update the INI preview."""
        # Generate preview from current configuration
        preview_lines = []
        preview_lines.append("[settings]")
        preview_lines.append(f"modname={self.ui.modNameEdit.text() or 'My Mod'}")
        preview_lines.append(f"author={self.ui.modAuthorEdit.text() or 'Unknown'}")
        preview_lines.append("")

        # TODO: Add actual configuration sections
        preview_lines.append("[GFF files]")
        preview_lines.append("; Files to be patched")
        preview_lines.append("")

        preview_lines.append("[2DAMEMORY]")
        preview_lines.append("; 2DA memory tokens")
        preview_lines.append("")

        preview_lines.append("[TLKList]")
        preview_lines.append("; TLK string additions")
        preview_lines.append("")

        self.ui.iniPreviewText.setPlainText("\n".join(preview_lines))

    def _preview_ini(self):
        """Show INI preview in current tab."""
        self.ui.configTabs.setCurrentIndex(self.ui.configTabs.indexOf(self.ui.configTabs.widget(self.ui.configTabs.count() - 1)))
        self._update_ini_preview()

    def _save_configuration(self):
        """Save the configuration to changes.ini."""
        ini_path = self.tslpatchdata_path / "changes.ini"

        # TODO: Actually build and save the INI file
        self._update_ini_preview()

        with open(ini_path, "w") as f:
            f.write(self.ui.iniPreviewText.toPlainText())

        from toolset.gui.common.localization import translate as tr, trf

        QMessageBox.information(
            self,
            tr("Saved"),
            trf("Configuration saved to:\n{path}", path=str(ini_path)),
        )

    def _generate_tslpatchdata(self):
        """Generate the complete TSLPatchData bundle."""
        if not self.tslpatchdata_path.exists():
            self.tslpatchdata_path.mkdir(parents=True)

        # Save configuration
        self._save_configuration()

        # TODO: Copy files to tslpatchdata folder
        # TODO: Generate namespaces.ini
        # TODO: Create installer executable

        from toolset.gui.common.localization import translate as tr, trf

        QMessageBox.information(
            self,
            tr("Generated"),
            trf("TSLPatchData generated at:\n{path}\n\nYou can now distribute this folder with HoloPatcher/TSLPatcher.", path=str(self.tslpatchdata_path)),
        )
