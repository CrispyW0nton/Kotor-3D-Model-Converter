"""Reusable standalone installation/folder-path toolbar for editor windows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from qtpy.QtCore import Signal  # pyright: ignore[reportPrivateImportUsage]
from qtpy.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from loggerplus import RobustLogger
from toolset.data.installation import HTInstallation
from toolset.gui.widgets.settings.installations import GlobalSettings, InstallationsWidget

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class FolderPathSpec:
    key: str
    label: str
    tooltip: str
    required: bool = False


class InstallationToolbar(QWidget):
    installation_changed = Signal(object)  # HTInstallation | None
    folder_paths_changed = Signal(object)  # dict[str, Path | None]

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        folder_path_specs: list[FolderPathSpec] | None = None,
        requires_installation: bool = False,
    ):
        super().__init__(parent)
        self._log = RobustLogger()
        self._specs: list[FolderPathSpec] = folder_path_specs or []
        self._requires_installation: bool = requires_installation
        self._settings = GlobalSettings()
        self._installation_cache: dict[str, HTInstallation] = {}
        self._folder_edits: dict[str, QLineEdit] = {}
        self._saved_installations: dict[str, dict[str, str | bool]] = {}
        self._in_update = False

        self._setup_ui()
        self.reload_installations()
        self._emit_current_state()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Installation:"))
        self.installation_combo = QComboBox(self)
        top_row.addWidget(self.installation_combo, 1)

        self.reload_btn = QPushButton("Reload", self)
        self.manage_btn = QPushButton("Manage...", self)
        top_row.addWidget(self.reload_btn)
        top_row.addWidget(self.manage_btn)
        root.addLayout(top_row)

        self.mode_row = QHBoxLayout()
        self.mode_full_radio = QRadioButton("Full installation", self)
        self.mode_folder_radio = QRadioButton("Specify folder paths", self)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.mode_full_radio)
        self.mode_group.addButton(self.mode_folder_radio)
        self.mode_row.addWidget(self.mode_full_radio)
        self.mode_row.addWidget(self.mode_folder_radio)
        self.mode_row.addStretch(1)
        root.addLayout(self.mode_row)

        self.paths_widget = QWidget(self)
        self.paths_layout = QFormLayout(self.paths_widget)
        self.paths_layout.setContentsMargins(0, 0, 0, 0)
        self.paths_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        root.addWidget(self.paths_widget)

        if not self._specs:
            self.mode_full_radio.setChecked(True)
            self.mode_folder_radio.hide()
            self.mode_full_radio.hide()
            self.paths_widget.hide()
        elif self._requires_installation:
            self.mode_full_radio.setChecked(True)
            self.mode_folder_radio.setEnabled(False)
            self.mode_folder_radio.setToolTip("This window requires a full installation.")
            self.paths_widget.hide()
        else:
            self.mode_full_radio.setChecked(True)
            self.paths_widget.hide()

        for spec in self._specs:
            row = QWidget(self.paths_widget)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)
            edit = QLineEdit(row)
            edit.setPlaceholderText("Optional folder path..." if not spec.required else "Required folder path...")
            edit.setToolTip(spec.tooltip)
            browse = QPushButton("Browse...", row)
            browse.clicked.connect(lambda _=False, key=spec.key: self._browse_for_path(key))
            edit.textChanged.connect(self._emit_current_state)
            row_layout.addWidget(edit, 1)
            row_layout.addWidget(browse)
            self._folder_edits[spec.key] = edit
            self.paths_layout.addRow(f"{spec.label}:", row)

        self.installation_combo.currentIndexChanged.connect(self._on_installation_selection_changed)
        self.reload_btn.clicked.connect(self.reload_installations)
        self.manage_btn.clicked.connect(self._open_installations_settings)
        self.mode_group.buttonToggled.connect(self._on_mode_changed)

    def reload_installations(self) -> None:
        current_key = self.installation_combo.currentData()
        self._saved_installations = {name: {"path": config.path, "tsl": config.tsl, "name": name} for name, config in self._settings.installations().items()}
        self._in_update = True
        try:
            self.installation_combo.clear()
            self.installation_combo.addItem("(None)", None)
            for name, config in sorted(self._saved_installations.items()):
                self.installation_combo.addItem(f"{name} ({config['path']})", name)
            if current_key is not None:
                idx = self.installation_combo.findData(current_key)
                if idx >= 0:
                    self.installation_combo.setCurrentIndex(idx)
        finally:
            self._in_update = False
        self._emit_current_state()

    def _browse_for_path(self, key: str) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select Folder")
        if directory:
            self._folder_edits[key].setText(directory)

    def _open_installations_settings(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Manage Installations")
        layout = QVBoxLayout(dialog)
        widget = InstallationsWidget(dialog)
        layout.addWidget(widget)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, dialog)
        layout.addWidget(button_box)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            widget.save()
            self.reload_installations()

    def _on_installation_selection_changed(self, _index: int) -> None:
        if self._in_update:
            return
        self._emit_current_state()

    def _on_mode_changed(self, _button, checked: bool) -> None:
        if not checked:
            return
        use_paths = self.mode_folder_radio.isChecked() and bool(self._specs) and not self._requires_installation
        self.paths_widget.setVisible(use_paths)
        self._emit_current_state()

    def _get_selected_installation(self) -> HTInstallation | None:
        selected_name = self.installation_combo.currentData()
        if selected_name is None:
            return None

        cache_key = str(selected_name)
        if cache_key in self._installation_cache:
            return self._installation_cache[cache_key]

        config = self._saved_installations.get(cache_key)
        if config is None:
            return None
        try:
            installation = HTInstallation(config["path"], config["name"], tsl=bool(config.get("tsl")))
            self._installation_cache[cache_key] = installation
            return installation
        except Exception as exc:  # noqa: BLE001
            self._log.exception("Failed to create installation '%s': %s", cache_key, exc)
            QMessageBox.warning(self, "Invalid Installation", f"Could not load installation '{cache_key}'.")
            return None

    def get_folder_paths(self) -> dict[str, Path | None]:
        result: dict[str, Path | None] = {}
        for spec in self._specs:
            raw = self._folder_edits[spec.key].text().strip()
            result[spec.key] = Path(raw) if raw else None
        return result

    def _emit_current_state(self) -> None:
        use_paths = self.mode_folder_radio.isChecked() and bool(self._specs) and not self._requires_installation
        selected_installation = None if use_paths else self._get_selected_installation()
        self.installation_changed.emit(selected_installation)
        self.folder_paths_changed.emit(self.get_folder_paths() if use_paths else {})


class StandaloneWindowMixin:
    STANDALONE_FOLDER_PATHS: ClassVar[list[FolderPathSpec]] = []
    STANDALONE_REQUIRES_INSTALLATION: ClassVar[bool] = False

    _installation_toolbar: InstallationToolbar | None = None
    _standalone_folder_paths: dict[str, Path | None]

    def enable_standalone_mode(self) -> None:
        if self._installation_toolbar is not None:
            return
        if not hasattr(self, "centralWidget"):
            return
        main_window = self
        if not isinstance(main_window, QWidget):  # runtime safety for pyright/mixin
            return
        central = getattr(main_window, "centralWidget")()
        if central is None:
            return

        self._standalone_folder_paths = {}
        self._installation_toolbar = InstallationToolbar(
            main_window,
            folder_path_specs=list(self.STANDALONE_FOLDER_PATHS),
            requires_installation=self.STANDALONE_REQUIRES_INSTALLATION,
        )
        self._installation_toolbar.installation_changed.connect(self._handle_installation_changed)
        self._installation_toolbar.folder_paths_changed.connect(self._handle_folder_paths_changed)

        container = QWidget(main_window)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._installation_toolbar)
        layout.addWidget(central, 1)
        getattr(main_window, "setCentralWidget")(container)

    def set_installation(self, installation: HTInstallation | None) -> None:
        setattr(self, "_installation", installation)
        self._on_installation_changed(installation)

    def _handle_installation_changed(self, installation: HTInstallation | None) -> None:
        setattr(self, "_installation", installation)
        self._on_installation_changed(installation)

    def _handle_folder_paths_changed(self, paths: dict[str, Path | None]) -> None:
        self._standalone_folder_paths = paths
        self._on_folder_paths_changed(paths)

    def _on_installation_changed(self, installation: HTInstallation | None) -> None:  # noqa: ARG002
        """Override in subclasses that need runtime installation switching."""

    def _on_folder_paths_changed(self, paths: dict[str, Path | None]) -> None:  # noqa: ARG002
        """Override in subclasses that support folder-path mode."""
