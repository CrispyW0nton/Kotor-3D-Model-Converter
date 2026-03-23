"""Base editor: common file/save/close, recent, and resource loading for all editors."""

from __future__ import annotations

import tempfile
import traceback
import uuid

from abc import abstractmethod
from contextlib import suppress
from pathlib import Path, PurePath
from typing import TYPE_CHECKING, Any, Callable, Optional, Sequence, cast

import qtpy

from qtpy.QtCore import (
    QBuffer,
    QIODevice,
    QTimer,
    Qt,
    Signal,  # pyright: ignore[reportPrivateImportUsage]
)
from qtpy.QtGui import QAction, QIcon, QPixmap
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,  # pyright: ignore[reportPrivateImportUsage]
    QPushButton,
    QShortcut,  # pyright: ignore[reportPrivateImportUsage]
    QStyle,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from loggerplus import RobustLogger  # pyright: ignore[reportMissingTypeStubs]
from pykotor.common.module import Module
from pykotor.extract.capsule import Capsule
from pykotor.extract.file import ResourceIdentifier
from pykotor.extract.installation import SearchLocation
from pykotor.resource.formats.bif import read_bif
from pykotor.resource.formats.erf import ERF, ERFType, read_erf, write_erf
from pykotor.resource.formats.gff import GFFStruct, bytes_gff, read_gff
from pykotor.resource.formats.rim import read_rim, write_rim
from pykotor.resource.type import ResourceType
from pykotor.tools.misc import is_any_erf_type_file, is_bif_file, is_capsule_file, is_rim_file, is_sav_file
from pykotor.tools.module import rim_to_mod
from toolset.data.installation import HTInstallation
from toolset.gui.common.localization import tr, trf
from toolset.gui.dialogs.load_from_module import LoadFromModuleDialog
from toolset.gui.dialogs.save.to_bif import BifSaveDialog, BifSaveOption
from toolset.gui.dialogs.save.to_module import SaveToModuleDialog
from toolset.gui.dialogs.save.to_rim import RimSaveDialog, RimSaveOption
from toolset.gui.widgets.edit.locstring import LocalizedStringLineEdit
from toolset.gui.widgets.installation_toolbar import StandaloneWindowMixin
from toolset.gui.widgets.media_player_widget import MediaPlayerWidget
from toolset.gui.widgets.settings.installations import GlobalSettings, InstallationsWidget
from utility.error_handling import format_exception_with_variables

if TYPE_CHECKING:
    import os

    from pathlib import PurePath

    from PyQt6.QtMultimedia import QMediaPlayer as PyQt6MediaPlayer  # pyright: ignore[reportMissingImports, reportAttributeAccessIssue]
    from PySide6.QtMultimedia import QMediaPlayer as PySide6MediaPlayer  # pyright: ignore[reportMissingImports, reportAttributeAccessIssue]
    from qtpy.QtCore import QRect
    from qtpy.QtGui import QScreen, _QAction
    from qtpy.QtWidgets import (
        QMenu,
        QMenuBar,
        QWidget,
    )
    from typing_extensions import Literal  # pyright: ignore[reportMissingModuleSource]

    from pykotor.common.language import LocalizedString
    from pykotor.resource.formats.bif import BIF
    from pykotor.resource.formats.gff import GFF
    from pykotor.resource.formats.rim import RIM
    from toolset.data.installation import HTInstallation


class Editor(QMainWindow, StandaloneWindowMixin):
    sig_new_file: Signal = Signal()
    sig_saved_file: Signal = Signal(str, str, ResourceType, bytes)
    sig_loaded_file: Signal = Signal(str, str, ResourceType, bytes)

    CAPSULE_FILTER: str = "*.mod *.erf *.rim *.sav *.bif"

    def __init__(  # noqa: PLR0913
        self,
        parent: QWidget | None,
        title: str,
        icon_name: str,
        read_supported: list[ResourceType],
        write_supported: list[ResourceType],
        installation: HTInstallation | None = None,
    ):
        super().__init__(parent)
        self._is_capsule_editor: bool = False
        self._installation: HTInstallation | None = installation
        self._logger: RobustLogger = RobustLogger()
        self._global_settings: GlobalSettings = GlobalSettings()

        self._editor_title: str = title
        self._restype: ResourceType = next(iter(read_supported or write_supported), ResourceType.INVALID)
        self._resname: str = f"untitled_{uuid.uuid4().hex[:8]}"
        self._filepath: Path = self.setup_extract_path() / f"{self._resname}.{self._restype.extension}"
        self._revert: bytes = b""
        self._is_save_game_resource: bool = False  # Flag to track if resource is from a save game

        self.media_player: MediaPlayerWidget = MediaPlayerWidget(self)
        self.setWindowTitle(title)
        self._setup_icon(icon_name)

        self.setup_editor_filters(read_supported, write_supported)

        # Installation toolbar — always visible, allows switching installation at any time.
        self._editor_toolbar: QToolBar = QToolBar(self)
        self._editor_toolbar.setObjectName("editorToolbar")
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._editor_toolbar)
        self._installation_combo: QComboBox | None = None
        self._installation_cache: dict[str, HTInstallation] = {}
        self._saved_installations: dict[str, dict[str, str | bool]] = {}
        self._installation_combo_in_update: bool = False
        self._folder_path_edits: dict[str, QLineEdit] = {}
        self._add_installation_combobox_to_toolbar(self._editor_toolbar)

        # Editors that declare STANDALONE_FOLDER_PATHS get a second toolbar row of folder path overrides.
        if self.STANDALONE_FOLDER_PATHS:
            self._folder_toolbar: QToolBar = QToolBar(self)
            self._folder_toolbar.setObjectName("folderPathsToolbar")
            self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._folder_toolbar)
            self._add_folder_path_inputs_to_toolbar(self._folder_toolbar)

    def _populate_editor_toolbar(self, toolbar: QToolBar) -> None:
        """Override in subclasses to append editor-specific controls after the installation combobox.

        The base class already adds the installation combobox (and folder path inputs for editors
        that declare STANDALONE_FOLDER_PATHS) automatically in __init__, so subclasses should NOT
        call _add_installation_combobox_to_toolbar here.
        """

    def enable_standalone_mode(self) -> None:
        """Editors always show installation controls in their toolbar; no extra panel needed."""

    def _add_folder_path_inputs_to_toolbar(self, toolbar: QToolBar) -> None:
        """Add a label + QLineEdit + Browse button for every FolderPathSpec declared by the editor."""
        for spec in self.STANDALONE_FOLDER_PATHS:
            toolbar.addWidget(QLabel(f"{spec.label}:"))
            edit = QLineEdit(self)
            edit.setPlaceholderText("(optional)" if not spec.required else "(required)")
            edit.setMinimumWidth(110)
            edit.setToolTip(spec.tooltip)
            toolbar.addWidget(edit)
            browse_btn = QPushButton("Browse...", self)
            browse_btn.clicked.connect(lambda _checked=False, k=spec.key: self._browse_folder_path(k))
            toolbar.addWidget(browse_btn)
            edit.editingFinished.connect(self._emit_folder_paths_changed)
            self._folder_path_edits[spec.key] = edit

    def _browse_folder_path(self, key: str) -> None:
        """Open a directory chooser and store the chosen path in the matching folder edit."""
        directory = QFileDialog.getExistingDirectory(self, "Select Folder")
        if directory and key in self._folder_path_edits:
            self._folder_path_edits[key].setText(directory)
            self._emit_folder_paths_changed()

    def _emit_folder_paths_changed(self) -> None:
        """Collect current folder path edit values and forward to _on_folder_paths_changed."""
        paths: dict[str, Path | None] = {
            spec.key: (Path(text) if (text := self._folder_path_edits[spec.key].text().strip()) else None)
            for spec in self.STANDALONE_FOLDER_PATHS
            if spec.key in self._folder_path_edits
        }
        self._on_folder_paths_changed(paths)

    def _add_installation_combobox_to_toolbar(self, toolbar: QToolBar) -> None:
        """Add Installation: combobox and Reload/Manage buttons to the editor toolbar."""
        toolbar.addWidget(QLabel("Installation:"))
        self._installation_combo = QComboBox(self)
        self._installation_combo.setMinimumWidth(180)
        toolbar.addWidget(self._installation_combo)
        reload_btn = QPushButton("Reload", self)
        reload_btn.clicked.connect(self._reload_installation_combo)
        toolbar.addWidget(reload_btn)
        manage_btn = QPushButton("Manage...", self)
        manage_btn.clicked.connect(self._open_installations_manage_dialog)
        toolbar.addWidget(manage_btn)
        self._reload_installation_combo()
        self._installation_combo.currentIndexChanged.connect(self._on_installation_combo_changed)

    def _reload_installation_combo(self) -> None:
        """Reload installation list from GlobalSettings and preserve current selection or set from self._installation."""
        if self._installation_combo is None:
            return
        current_key = self._installation_combo.currentData()
        self._saved_installations = {name: {"path": config.path, "tsl": config.tsl, "name": name} for name, config in self._global_settings.installations().items()}
        self._installation_combo_in_update = True
        try:
            self._installation_combo.clear()
            self._installation_combo.addItem("(None)", None)
            for name, config in sorted(self._saved_installations.items()):
                self._installation_combo.addItem(f"{name} ({config['path']})", name)
            if self._installation is not None:
                key = self._installation.name
                idx = self._installation_combo.findData(key)
                if idx >= 0:
                    self._installation_combo.setCurrentIndex(idx)
            elif current_key is not None:
                idx = self._installation_combo.findData(current_key)
                if idx >= 0:
                    self._installation_combo.setCurrentIndex(idx)
        finally:
            self._installation_combo_in_update = False

    def _open_installations_manage_dialog(self) -> None:
        """Open Manage Installations dialog and reload combobox on save."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Manage Installations")
        layout = QVBoxLayout(dialog)
        widget = InstallationsWidget(dialog)
        layout.addWidget(widget)
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            dialog,
        )
        layout.addWidget(button_box)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            widget.save()
            self._reload_installation_combo()

    def _on_installation_combo_changed(self, _index: int) -> None:
        """Resolve selected installation and call _on_installation_changed."""
        if self._installation_combo_in_update:
            return
        installation = self._get_installation_from_combo()
        self._installation = installation
        self._on_installation_changed(installation)

    def _get_installation_from_combo(self) -> HTInstallation | None:
        """Resolve current combobox selection to HTInstallation."""
        if self._installation_combo is None:
            return None
        selected_name: str | None = self._installation_combo.currentData()
        if selected_name is None:
            return None
        cache_key: str = str(selected_name)
        if cache_key in self._installation_cache:
            return self._installation_cache[cache_key]
        config: dict[str, Any] | None = self._saved_installations.get(cache_key)
        if config is None:
            return None
        try:
            installation = HTInstallation(
                str(config["path"]),
                str(config["name"]),
                tsl=bool(config.get("tsl") or False),
            )
            self._installation_cache[cache_key] = installation
            return installation
        except Exception as exc:
            self._logger.exception("Failed to create installation '%s': %s", cache_key, exc)
            QMessageBox.warning(
                self,
                "Invalid Installation",
                f"Could not load installation '{cache_key}'.",
            )
            return None

    def _on_installation_changed(self, installation: HTInstallation | None) -> None:
        """Override in subclasses that need to react to installation changes."""
        return

    @abstractmethod
    def build(self) -> tuple[bytes | bytearray, bytes | bytearray]: ...

    def _setup_menus(self):
        menubar: QMenuBar | None = self.menuBar()
        assert menubar is not None, "menubar is somehow None"

        # If menubar is empty, create a File menu with standard actions
        if not menubar.actions():
            file_menu = QMenu("File", self)
            menubar.addMenu(file_menu)

            # Create standard file menu actions
            new_action = QAction("New", self)
            new_action.setShortcut("Ctrl+N")
            new_action.triggered.connect(self.new)
            file_menu.addAction(new_action)

            open_action = QAction("Open", self)
            open_action.setShortcut("Ctrl+O")
            open_action.triggered.connect(self.open)
            file_menu.addAction(open_action)

            save_action = QAction("Save", self)
            save_action.setShortcut("Ctrl+S")
            save_action.triggered.connect(self.save)
            file_menu.addAction(save_action)

            save_as_action = QAction("Save As", self)
            save_as_action.setShortcut("Ctrl+Shift+S")
            save_as_action.triggered.connect(self.save_as)
            file_menu.addAction(save_as_action)

            file_menu.addSeparator()

            revert_action = QAction("Revert", self)
            revert_action.setShortcut("Ctrl+R")
            revert_action.triggered.connect(self.revert)
            file_menu.addAction(revert_action)

            file_menu.addSeparator()

            exit_action = QAction("Exit", self)
            exit_action.setShortcut("Ctrl+Q")
            # QAction.triggered emits a bool; QWidget.close takes no args.
            exit_action.triggered.connect(lambda *_: self.close())
            file_menu.addAction(exit_action)
        else:
            # Menubar already has menus (from UI file), connect to existing actions
            menubar_menu = menubar.actions()[0].menu()
            if not isinstance(menubar_menu, QMenu):
                raise TypeError(f"self.menuBar().actions()[0].menu() returned a {type(menubar_menu).__name__} object, expected QMenu.")
            for action in menubar_menu.actions():
                if action.text() == "New":
                    action.triggered.connect(self.new)
                    action.setShortcut("Ctrl+N")
                if action.text() == "Open":
                    action.triggered.connect(self.open)
                    action.setShortcut("Ctrl+O")
                if action.text() == "Save":
                    action.triggered.connect(self.save)
                    action.setShortcut("Ctrl+S")
                if action.text() == "Save As":
                    action.triggered.connect(self.save_as)
                    action.setShortcut("Ctrl+Shift+S")
                if action.text() == "Revert":
                    action.triggered.connect(self.revert)
                    action.setShortcut("Ctrl+R")
                if action.text() == "Exit":
                    # QAction.triggered emits a bool; QWidget.close takes no args.
                    action.triggered.connect(lambda *_: self.close())
                    action.setShortcut("Ctrl+Q")

    def _add_help_action(self, wiki_filename: str | None = None):
        """Add a help action to the menu bar with question mark icon.

        Args:
            wiki_filename: Name of the markdown file in the wiki directory (e.g., "GFF-File-Format.md").
                          If None, will try to auto-detect from editor class name.
        """
        from toolset.gui.editors.editor_wiki_mapping import EDITOR_WIKI_MAP

        # Auto-detect wiki file if not provided
        if wiki_filename is None:
            editor_class_name = self.__class__.__name__
            wiki_filename = EDITOR_WIKI_MAP.get(editor_class_name)
            if wiki_filename is None:
                # No wiki file for this editor, skip adding help
                return

        menubar: QMenuBar | None = self.menuBar()
        assert menubar is not None, "menubar is somehow None"
        help_menu: QMenu | None = None

        # Check if Help menu already exists
        for action in menubar.actions():
            if action.text() == "Help":
                help_menu = action.menu()
                break

        # Create Help menu if it doesn't exist
        if help_menu is None:
            help_menu = QMenu("Help", self)
            menubar.addMenu(help_menu)

        # Check if Documentation action already exists (idempotent)
        doc_action = None
        for action in help_menu.actions():
            if action.text() == "Documentation":
                doc_action = action
                break

        # Only add if it doesn't exist
        if doc_action is None:
            # Add help action with question mark icon
            style: QStyle | None = self.style()
            if style is not None:
                help_icon = style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion)
            else:
                help_icon = QIcon()

            help_action = help_menu.addAction(help_icon, "Documentation")
            assert help_action is not None, "help_action is somehow None"
            help_action.setShortcut("F1")
            help_action.triggered.connect(lambda: self._show_help_dialog(wiki_filename))

            QShortcut("F1", self).activated.connect(lambda: self._show_help_dialog(wiki_filename))

    def _show_help_dialog(self, wiki_filename: str):
        """Show the help dialog for this editor.

        Args:
            wiki_filename: Name of the markdown file in the wiki directory
        """
        from toolset.gui.dialogs.editor_help import EditorHelpDialog

        # Create non-blocking dialog
        dialog = EditorHelpDialog(self, wiki_filename)
        dialog.show()  # Non-blocking show

    def _setup_icon(
        self,
        icon_resname: str,
    ):
        icon_version: Literal["x", "2", "1"] = "x" if self._installation is None else "2" if self._installation.tsl else "1"
        icon_path_str: str = f":/images/icons/k{icon_version}/{icon_resname}.png"
        self.setWindowIcon(QIcon(QPixmap(icon_path_str)))

    def setup_extract_path(self) -> Path:
        extract_path: Path = Path(GlobalSettings().extractPath)
        if extract_path.exists() and extract_path.is_dir():
            return extract_path
        extract_path = Path(tempfile.mkdtemp(prefix="holocron_toolset_"))
        GlobalSettings().extractPath = str(extract_path)
        return extract_path

    def refresh_window_title(self):
        """Refreshes the window title based on the current state of the editor."""
        installation_name: str = self._installation.name if self._installation else tr("No Installation")
        title: str = trf("{editor_title}({installation_name})[*]", editor_title=self._editor_title, installation_name=installation_name)
        if self._filepath and self._resname and self._restype:
            relpath: Path = self._filepath.relative_to(self._filepath.parent.parent) if self._filepath.parent.parent.name else self._filepath.parent
            from toolset.gui.editors.erf import ERFEditor

            if (is_bif_file(relpath) or is_capsule_file(self._filepath)) and not isinstance(self, ERFEditor):
                relpath /= f"{self._resname}.{self._restype.extension}"
            title = trf("{relpath} - {title}", relpath=relpath, title=title)
        self.setWindowTitle(title)

    def setup_editor_filters(
        self,
        read_supported: list[ResourceType],
        write_supported: list[ResourceType],
    ):
        write_supported = read_supported.copy() if read_supported is write_supported else write_supported
        additional_formats: set[str] = {"XML", "JSON", "CSV", "ASCII", "YAML"}
        for add_format in additional_formats:
            read_supported.extend(
                ResourceType.__members__[f"{restype.name}_{add_format}"]
                for restype in read_supported
                if f"{restype.name}_{add_format}" in ResourceType.__members__  # noqa: E501
            )
            write_supported.extend(
                ResourceType.__members__[f"{restype.name}_{add_format}"]
                for restype in write_supported
                if f"{restype.name}_{add_format}" in ResourceType.__members__  # noqa: E501
            )
        self._read_supported: list[ResourceType] = read_supported
        self._write_supported: list[ResourceType] = write_supported

        self._save_filter: str = tr("All valid files (")
        for resource in write_supported:
            self._save_filter += f"*.{resource.extension}{'' if write_supported[-1] == resource else ' '}"
        self._save_filter += f" {self.CAPSULE_FILTER});;"
        for resource in write_supported:
            self._save_filter += f"{resource.category} File (*.{resource.extension});;"
        self._save_filter += trf("Save into module ({capsule_filter})", capsule_filter=self.CAPSULE_FILTER)

        self._open_filter: str = tr("All valid files (")
        for resource in read_supported:
            self._open_filter += f"*.{resource.extension}{'' if read_supported[-1] == resource else ' '}"
        self._open_filter += f" {self.CAPSULE_FILTER});;"
        for resource in read_supported:
            self._open_filter += f"{resource.category} File (*.{resource.extension});;"
        self._open_filter += trf("Load from module ({capsule_filter})", capsule_filter=self.CAPSULE_FILTER)

    def save_as(self):  # noqa: C901
        def show_invalid(exc: Exception | None, msg: str):
            msgBox = QMessageBox(
                QMessageBox.Icon.Critical,
                tr("Invalid filename/extension"),
                trf("Check the filename and try again. Could not save!{msg}", msg=f'<br><br>{msg}' if msg else ''),
                parent=None,
                flags=Qt.WindowType.Window | Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint,
            )
            if exc is not None:
                msgBox.setDetailedText(traceback.format_exc())
            msgBox.exec()

        filepath_str, _filter = QFileDialog.getSaveFileName(self, "Save As", str(self._filepath), self._save_filter, "")
        if not filepath_str:
            return
        error_msg, exc = "", None
        try:
            identifier = ResourceIdentifier.from_path(filepath_str)
            if identifier.restype.is_invalid:
                show_invalid(None, str(identifier))
                return
        except ValueError as e:
            exc = e
            RobustLogger().exception(f"ValueError raised, assuming invalid filename/extension '{filepath_str}'")
            error_msg = str((e.__class__.__name__, str(e))).replace("\n", "<br>")
            show_invalid(exc, error_msg)
            return

        if is_capsule_file(filepath_str) and f"Save into module ({self.CAPSULE_FILTER})" in self._save_filter:
            if self._resname is None or self._restype is None:
                self._resname = "new"
                self._restype = self._write_supported[0]

            dialog2 = SaveToModuleDialog(self._resname, self._restype, self._write_supported)
            if dialog2.exec():
                self._resname = dialog2.resname()
                self._restype = dialog2.restype()
                self._filepath = Path(filepath_str)
        else:
            self._filepath = Path(filepath_str)
            self._resname, self._restype = identifier.unpack()
        self.save()

        self.refresh_window_title()
        menu_bar: QMenuBar | None = self.menuBar()
        assert menu_bar is not None, "menu_bar is somehow None"
        menu: QMenu | None = menu_bar.actions()[0].menu()
        assert menu is not None, "menu is somehow None"
        for action in menu.actions():
            if action.text() == "Revert":
                action.setEnabled(True)

    def save(self):
        if self._filepath is None:
            self.save_as()
            return

        try:
            data, data_ext = self.build()
            if data is None:
                return
            from toolset.gui.editors.gff import GFFEditor

            # HACK: Write a real implementation for this later, and remove this hack.
            # CRITICAL: For save game resources, ALWAYS preserve extra fields
            # Save game GFF files contain undocumented fields that must be preserved
            # to prevent save corruption. This is more important than the user setting.
            should_preserve_fields: bool = self._is_save_game_resource or self._global_settings.attemptKeepOldGFFFields

            if should_preserve_fields and self._restype is not None and self._restype.is_gff() and not isinstance(self, GFFEditor) and self._revert is not None:  # noqa: E501
                if self._is_save_game_resource:
                    print("Save game resource detected: Preserving all extra GFF fields to prevent save corruption.")
                old_gff: GFF = read_gff(self._revert)
                new_gff: GFF = read_gff(data)
                GFFStruct._add_missing(new_gff.root, old_gff.root)
                data: bytes = bytes_gff(new_gff)
            self._revert = data

            self.refresh_window_title()

            if is_bif_file(self._filepath):
                self._save_ends_with_bif(data, data_ext)
            elif is_capsule_file(self._filepath.parent):
                self._save_nested_capsule(data, data_ext)
            elif is_rim_file(self._filepath.name):
                self._save_ends_with_rim(data, data_ext)
            elif is_any_erf_type_file(self._filepath):
                self._save_ends_with_erf(data, data_ext)
            else:
                self._save_ends_with_other(data, data_ext)
        except Exception as e:  # noqa: BLE001
            self.blink_window()
            RobustLogger().critical(tr("Failed to write to file"), exc_info=True)
            msg_box = QMessageBox(QMessageBox.Icon.Critical, tr("Failed to write to file"), trf("{class_name}: {error}", class_name=e.__class__.__name__, error=str(e)).replace("\n", "<br>"))
            msg_box.setDetailedText(format_exception_with_variables(e))
            msg_box.exec()
        else:
            self.setWindowModified(False)

    def _save_ends_with_bif(
        self,
        data: bytes,
        data_ext: bytes,
    ):
        dialog = BifSaveDialog(self)
        dialog.exec()
        if dialog.option == BifSaveOption.MOD:
            str_filepath, filter = QFileDialog.getSaveFileName(
                self,
                tr("Save As"),
                "",
                tr(".MOD File (*.mod)"),
                "",
                options=QFileDialog.Option.DontUseNativeDialog,
            )
            if str_filepath is None or not str(str_filepath).strip():
                return
            r_filepath: Path = Path(str_filepath)
            dialog2 = SaveToModuleDialog(self._resname, self._restype, self._write_supported)
            if dialog2.exec():
                self._resname = dialog2.resname()
                self._restype = dialog2.restype()
                self._filepath = r_filepath
                self.save()
        elif dialog.option == BifSaveOption.Override:
            assert self._installation is not None
            self._filepath = self._installation.override_path() / f"{self._resname}.{self._restype.extension}"
            self.save()

    def _save_ends_with_rim(
        self,
        data: bytes,
        data_ext: bytes,
    ):
        if self._global_settings.disableRIMSaving:
            dialog = RimSaveDialog(self)
            dialog.exec()
            if dialog.option == RimSaveOption.MOD:
                self._filepath = self._filepath.parent / f"{Module.filepath_to_root(self._filepath)}.mod"
                self.save()
            elif dialog.option == RimSaveOption.Override:
                assert self._installation is not None
                self._filepath = self._installation.override_path() / f"{self._resname}.{self._restype.extension}"
                self.save()
            return

        rim: RIM = read_rim(self._filepath)

        if self._restype == ResourceType.MDL:
            rim.set_data(self._resname, ResourceType.MDX, data_ext)

        rim.set_data(self._resname, self._restype, data)

        write_rim(rim, self._filepath)
        self.sig_saved_file.emit(str(self._filepath), self._resname, self._restype, bytes(data))

        if self._installation is not None:
            self._installation.reload_module(self._filepath.name)

    def _save_nested_capsule(
        self,
        data: bytes | bytearray,
        data_ext: bytes,
    ):
        nested_paths: list[PurePath] = []
        if is_any_erf_type_file(self._filepath) or is_rim_file(self._filepath):
            nested_paths.append(self._filepath)

        r_parent_filepath: Path = self._filepath.parent
        while (
            (
                ResourceType.from_extension(r_parent_filepath.suffix).name
                in (
                    ResourceType.ERF,
                    ResourceType.MOD,
                    ResourceType.SAV,
                    ResourceType.RIM,
                    ResourceType.BIF,
                )
            )
            and not r_parent_filepath.exists()
            and not r_parent_filepath.is_dir()
        ):
            nested_paths.append(r_parent_filepath)
            self._filepath = r_parent_filepath
            r_parent_filepath = self._filepath.parent

        det_restype: ResourceType = ResourceType.from_extension(r_parent_filepath.suffix)
        if det_restype == ResourceType.RIM:
            bioware_archive = read_rim(self._filepath)
        elif det_restype == ResourceType.ERF:
            bioware_archive = read_erf(self._filepath)
        elif det_restype == ResourceType.BIF:
            bioware_archive = read_bif(self._filepath)
        else:
            raise ValueError(f"Unexpected resource type: {det_restype}")
        nested_capsules: list[tuple[PurePath, ERF | RIM | BIF]] = [
            (
                self._filepath,
                bioware_archive,
            )
        ]
        for capsule_path in reversed(nested_paths[:-1]):
            nested_erf_or_rim_data: bytes | None = bioware_archive.get(
                capsule_path.stem,
                ResourceType.from_extension(capsule_path.suffix),
            )
            if nested_erf_or_rim_data is None:
                msg: str = f"You must save the ERFEditor for '{capsule_path.relative_to(r_parent_filepath)}' to before modifying its nested resources. Do so and try again."
                raise ValueError(msg)

            bioware_archive = read_rim(nested_erf_or_rim_data) if ResourceType.from_extension(capsule_path.suffix) == ResourceType.RIM else read_erf(nested_erf_or_rim_data)
            nested_capsules.append((capsule_path, bioware_archive))

        this_erf_or_rim = None
        for index, (_capsule_path, this_erf_or_rim) in enumerate(reversed(nested_capsules)):
            if index == 0:
                if not self._is_capsule_editor:
                    this_erf_or_rim.set_data(self._resname, self._restype, bytes(data))
                continue
            child_index: int = len(nested_capsules) - index
            child_capsule_path, child_erf_or_rim = nested_capsules[child_index]
            if self._filepath != child_capsule_path or not self._is_capsule_editor:
                data = bytearray()
                write_erf(child_erf_or_rim, data) if isinstance(child_erf_or_rim, ERF) else write_rim(child_erf_or_rim, data)
            this_erf_or_rim.set_data(child_capsule_path.stem, ResourceType.from_extension(child_capsule_path.suffix), bytes(data))

        assert this_erf_or_rim is not None, "this_erf_or_rim is None somehow? This should be impossible."
        write_erf(this_erf_or_rim, self._filepath) if isinstance(this_erf_or_rim, ERF) else write_rim(this_erf_or_rim, self._filepath)
        self.sig_saved_file.emit(str(self._filepath), self._resname, self._restype, bytes(data))

    def _save_ends_with_erf(
        self,
        data: bytes,
        data_ext: bytes,
    ):
        erftype: ERFType = ERFType.from_extension(self._filepath)

        if self._filepath.is_file():
            erf: ERF = read_erf(self._filepath)
        elif self._filepath.with_suffix(".rim").is_file():
            rim_to_mod(self._filepath)
            erf = read_erf(self._filepath)
        else:
            print(trf("Saving '{resname}.{restype}' to a blank new {erftype_name} file at '{filepath}'", resname=self._resname, restype=self._restype, erftype_name=erftype.name, filepath=self._filepath))
            erf = ERF(erftype)
        erf.erf_type = erftype

        if self._restype == ResourceType.MDL:
            erf.set_data(self._resname, ResourceType.MDX, data_ext)

        erf.set_data(self._resname, self._restype, data)

        write_erf(erf, self._filepath)
        self.sig_saved_file.emit(str(self._filepath), self._resname, self._restype, bytes(data))
        if self._installation is not None and self._filepath.parent == self._installation.module_path():
            self._installation.reload_module(self._filepath.name)

    def _save_ends_with_other(
        self,
        data: bytes,
        data_ext: bytes,
    ):
        self._filepath.write_bytes(data)
        if self._restype == ResourceType.MDL:
            self._filepath.with_suffix(".mdx").write_bytes(data_ext)
        self.sig_saved_file.emit(str(self._filepath), self._resname, self._restype, bytes(data))

    def open(self):
        filepath_str, _filter = QFileDialog.getOpenFileName(self, "Open file", "", self._open_filter, "")
        if filepath_str is None or not str(filepath_str).strip():
            return
        r_filepath = Path(filepath_str)

        if is_capsule_file(r_filepath) and f"Load from module ({self.CAPSULE_FILTER})" in self._open_filter:
            self._load_module_from_dialog_info(r_filepath)
        else:
            data: bytes = r_filepath.read_bytes()
            res_ident: ResourceIdentifier = ResourceIdentifier.from_path(r_filepath).validate()
            self.load(r_filepath, res_ident.resname, res_ident.restype, data)

    def _load_module_from_dialog_info(
        self,
        r_filepath: Path,
    ):
        dialog = LoadFromModuleDialog(Capsule(r_filepath), self._read_supported)
        if dialog.exec():
            resname: str | None = dialog.resname()
            restype: ResourceType | None = dialog.restype()
            data: bytes | None = dialog.data()
            assert resname is not None
            assert restype is not None
            assert data is not None
            self.load(r_filepath, resname, restype, data)

    def center_and_adjust_window(self):
        primary_screen: QScreen | None = QApplication.primaryScreen()
        if primary_screen is None:
            return
        screen: QRect = primary_screen.geometry()
        new_x: int = (screen.width() - self.width()) // 2
        new_y: int = (screen.height() - self.height()) // 2

        self.move(
            max(0, min(new_x, screen.width() - self.width())),
            max(0, min(new_y, screen.height() - self.height())),
        )

    def load(
        self,
        filepath: os.PathLike | str,
        resref: str,
        restype: ResourceType,
        data: bytes | bytearray,
    ):
        self._filepath = Path(filepath)
        self._resname = resref
        self._restype = restype
        # Convert bytearray to bytes if needed
        data_bytes = bytes(data) if isinstance(data, bytearray) else data
        self._revert = data_bytes

        # Detect if this resource is from a save game
        # Check if any parent in the filepath is a .sav file
        self._is_save_game_resource = self._detect_save_game_resource(self._filepath)

        menu_bar: QMenuBar | None = cast("Optional[QMenuBar]", self.menuBar())
        assert menu_bar is not None, "Menu bar is None somehow? This should be impossible."
        menu_bar_actions: Sequence[_QAction] = menu_bar.actions()  # pyright: ignore[reportAssignmentType]
        if len(menu_bar_actions) > 0:
            menu: QMenu | None = menu_bar_actions[0].menu()
            assert menu is not None, "Menu is somehow None"
            for action in menu_bar_actions:
                if action.text() == "Revert":
                    action.setEnabled(True)
                    break
        self.refresh_window_title()
        self.sig_loaded_file.emit(str(self._filepath), self._resname, self._restype, data_bytes)

    def _detect_save_game_resource(self, filepath: Path) -> bool:
        """Detect if a resource is from a save game by checking the filepath.

        Save game resources are nested inside SAVEGAME.sav or cached module .sav files.
        This method checks if any parent in the path is a .sav file.

        Args:
        ----
            filepath: Path to check

        Returns:
        -------
            bool: True if resource is from a save game, False otherwise
        """
        current_path = filepath
        while current_path != current_path.parent:
            # Check if current path component is a .sav file
            if is_sav_file(current_path):
                return True
            # Check if parent is a .sav file (for nested resources)
            if is_sav_file(current_path.parent):
                return True
            current_path = current_path.parent
            # Stop if we've reached the root
            if not current_path.parts:
                break
        return False

    def new(self):
        self._revert = b""
        self._is_save_game_resource = False
        self._resname = f"untitled_{uuid.uuid4().hex[:8]}"
        self._filepath = self.setup_extract_path() / f"{self._resname}.{self._restype.extension}"
        menu_bar: QMenuBar | None = cast("Optional[QMenuBar]", self.menuBar())
        assert menu_bar is not None, "Menu bar is None somehow? This should be impossible."
        menu: QMenu | None = menu_bar.actions()[0].menu()
        assert menu is not None, "Menu is somehow None"
        menu_bar_actions: Sequence[_QAction] = menu.actions()  # pyright: ignore[reportAssignmentType]
        if len(menu_bar_actions) > 0:
            for action in menu_bar_actions:
                if action.text() != "Revert":
                    continue
                action.setEnabled(False)
        self.refresh_window_title()
        self.sig_new_file.emit()

    def revert(self):
        if self._revert is None:
            print("No data to revert from")
            self.blink_window()
            return
        self.load(self._filepath, self._resname, self._restype, self._revert)

    def _load_locstring(
        self,
        textbox: QLineEdit | QPlainTextEdit | LocalizedStringLineEdit,
        locstring: LocalizedString,
    ):
        if isinstance(textbox, LocalizedStringLineEdit):
            textbox.set_locstring(locstring)
            return
        setText: Callable[[str], None] = textbox.setPlainText if isinstance(textbox, QPlainTextEdit) else textbox.setText

        from toolset.gui.common.style.palette_utils import apply_locstring_background

        if locstring.stringref == -1:
            text = str(locstring)
            setText(text if text != "-1" else "")
            apply_locstring_background(textbox, from_tlk=False)
        elif self._installation is not None:
            setText(self._installation.talktable().string(locstring.stringref))
            apply_locstring_background(textbox, from_tlk=True)
        textbox.locstring = locstring  # type: ignore[attr-defined]

    def blink_window(
        self,
        *,
        sound: bool = True,
    ):
        if sound:
            with suppress(Exception):
                self.play_sound("dr_metal_lock")
        self.setWindowOpacity(0.7)
        QTimer.singleShot(125, lambda: self.setWindowOpacity(1))

    def play_byte_source_media(
        self,
        data: bytes | None,
    ) -> bool:
        if not data:
            self.blink_window()
            return False
        if qtpy.QT5:
            from qtpy.QtMultimedia import QMediaContent  # pyright: ignore[reportAttributeAccessIssue]

            self.media_player.buffer = buffer = QBuffer(self)
            buffer.setData(data)
            buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            self.media_player.player.setMedia(QMediaContent(), buffer)  # pyright: ignore[reportAttributeAccessIssue]
            QTimer.singleShot(0, self.media_player.player.play)

        elif qtpy.QT6:
            from qtpy.QtMultimedia import QAudioOutput  # pyright: ignore[reportAttributeAccessIssue]

            # Create buffer and load data
            buffer = QBuffer(self)
            buffer.setData(data)
            buffer.open(QIODevice.OpenModeFlag.ReadOnly)

            # Set up player
            player: PyQt6MediaPlayer | PySide6MediaPlayer = cast("Any", self.media_player.player)
            audio_output = QAudioOutput(self)
            audio_output.setVolume(1)
            player.setAudioOutput(audio_output)

            # Use the buffer directly instead of a file
            player.setSourceDevice(buffer)
            player.play()
        return True

    def play_sound(
        self,
        resname: str,
        order: list[SearchLocation] | None = None,
    ) -> bool:
        """Plays a sound resource."""
        if not resname or not resname.strip() or self._installation is None:
            self.blink_window(sound=False)
            return False

        self.media_player.player.stop()

        data: bytes | None = self._installation.sound(
            resname,
            order
            if order is not None
            else [
                SearchLocation.MUSIC,
                SearchLocation.VOICE,
                SearchLocation.SOUND,
                SearchLocation.OVERRIDE,
                SearchLocation.CHITIN,
            ],
        )
        if not data:
            self.blink_window(sound=False)
        return self.play_byte_source_media(data)

    def filepath(self) -> str | None:
        return str(self._filepath)
