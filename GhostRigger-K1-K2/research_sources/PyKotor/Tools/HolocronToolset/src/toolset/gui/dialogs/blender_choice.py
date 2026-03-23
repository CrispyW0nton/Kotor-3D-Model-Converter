"""Dialog for choosing between Blender and built-in editor.

This dialog is shown when the user opens a module/GIT and Blender is available,
allowing them to choose which editor to use.
"""

from __future__ import annotations

import platform

from pathlib import Path
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
)

from toolset.blender import detect_blender, get_blender_settings
from toolset.blender.detection import (
    find_all_blender_installations,
    install_kotorblender,
)

if TYPE_CHECKING:
    from qtpy.QtWidgets import QLayout, QWidget
    from typing_extensions import Literal

    from toolset.blender import BlenderInfo


def _get_semantic_colors() -> dict[str, str]:
    """Get semantic colors from the application palette.

    Returns:
        Dictionary with keys: 'success', 'warning', 'error', 'muted'
    """
    # Use common helper function for consistency
    from toolset.gui.common.palette_helpers import get_semantic_colors

    return get_semantic_colors()


class BlenderChoiceDialog(QDialog):
    """Dialog for choosing between Blender and built-in editor.

    Shows when:
    - Blender is detected
    - kotorblender is installed
    - User hasn't chosen to remember their preference
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        blender_info: BlenderInfo | None = None,
        context: str = "Module Designer",
    ):
        super().__init__(parent)

        self._blender_info = blender_info or detect_blender()
        self._all_installations: list[BlenderInfo] = []
        self._context: str = context
        self._choice: Literal["blender", "builtin"] = "builtin"  # "blender" or "builtin"
        self._install_button: QPushButton | None = None
        self._warning_label: QLabel | None = None
        self._install_hint_label: QLabel | None = None

        self._setup_ui()

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

    @property
    def choice(self) -> str:
        """Get the user's choice: 'blender' or 'builtin'."""
        return self._choice

    @property
    def remember_choice(self) -> bool:
        """Check if user wants to remember their choice."""
        return self.ui.rememberCheckbox.isChecked()

    def _setup_ui(self):
        """Setup the dialog UI."""
        from toolset.uic.qtpy.dialogs.blender_choice import Ui_Dialog

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        # Update question label with context
        self.ui.questionLabel.setText(f"<b>How would you like to open the {self._context}?</b>")

        # Store reference to info layout for dynamic content
        self._info_layout: QLayout = self.ui.infoLayout
        self._info_frame: QFrame = self.ui.infoFrame

        # Update button states and connect signals
        self._update_blender_button_state()
        self.ui.blenderButton.clicked.connect(self._choose_blender)
        self.ui.builtinButton.clicked.connect(self._choose_builtin)
        self.ui.cancelButton.clicked.connect(lambda: self.reject())

        # Update Blender info display
        self._update_blender_info_display()

    def _update_blender_info_display(self):
        """Update the Blender info display based on current state."""
        # Clear existing widgets
        while self._info_layout.count():
            item = self._info_layout.takeAt(0)
            if item is not None and item.widget():
                item.widget().deleteLater()  # pyright: ignore[reportOptionalMemberAccess]
            elif item is not None and item.layout():
                # Clear nested layouts
                while item is not None and item.layout().count():  # pyright: ignore[reportOptionalMemberAccess]
                    nested_item = item.layout().takeAt(0)  # pyright: ignore[reportOptionalMemberAccess]
                    if nested_item is not None and nested_item.widget():
                        nested_item.widget().deleteLater()  # pyright: ignore[reportOptionalMemberAccess]

        colors = _get_semantic_colors()

        if self._blender_info.is_valid:
            # Blender found - show status
            status_label = QLabel(f"<b>Blender {self._blender_info.version_string}</b> detected")
            status_label.setStyleSheet(f"color: {colors['success']};")
            self._info_layout.addWidget(status_label)

            path_label = QLabel(f"<small>{self._blender_info.executable}</small>")
            path_label.setWordWrap(True)
            path_label.setStyleSheet(f"color: {colors['muted']};")
            self._info_layout.addWidget(path_label)

            if self._blender_info.has_kotorblender:
                # kotorblender installed - all good
                addon_label = QLabel(f"<b>kotorblender {self._blender_info.kotorblender_version}</b> installed")
                addon_label.setStyleSheet(f"color: {colors['success']};")
                self._info_layout.addWidget(addon_label)
            else:
                # kotorblender missing - show warning and install option
                self._warning_label = QLabel(f"<span style='color: {colors['warning']};'><b>Warning:</b> kotorblender not found</span>")
                self._info_layout.addWidget(self._warning_label)

                self._install_hint_label = QLabel("<small>kotorblender is required to use Blender. Install it to enable the Blender option.</small>")
                self._install_hint_label.setWordWrap(True)
                self._install_hint_label.setStyleSheet(f"color: {colors['muted']};")
                self._info_layout.addWidget(self._install_hint_label)

                # Install buttons
                install_button_layout = QHBoxLayout()
                install_button_layout.addStretch()

                self._install_button = QPushButton("Install kotorblender")
                self._install_button.clicked.connect(self._install_kotorblender)
                self._install_button.setToolTip("Automatically install kotorblender from bundled source")
                install_button_layout.addWidget(self._install_button)

                browse_addon_btn = QPushButton("Browse...")
                browse_addon_btn.clicked.connect(self._browse_kotorblender)
                browse_addon_btn.setToolTip("Manually select kotorblender folder (io_scene_kotor)")
                install_button_layout.addWidget(browse_addon_btn)

                install_button_layout.addStretch()
                self._info_layout.addLayout(install_button_layout)

            # Show other installations if available
            self._all_installations = find_all_blender_installations()
            if len(self._all_installations) > 1:
                self._add_installation_selector()

        else:
            # No Blender found - show error and browse option
            error_label = QLabel(f"<span style='color: {colors['error']};'><b>Blender not found</b></span>")
            self._info_layout.addWidget(error_label)

            hint_label = QLabel("<small>Install Blender 3.6 or later, or browse to an existing installation.</small>")
            hint_label.setWordWrap(True)
            hint_label.setStyleSheet(f"color: {colors['muted']};")
            self._info_layout.addWidget(hint_label)

            # Browse button
            browse_layout = QHBoxLayout()
            browse_layout.addStretch()

            browse_btn = QPushButton("Browse for Blender...")
            browse_btn.clicked.connect(self._browse_blender)
            browse_layout.addWidget(browse_btn)

            browse_layout.addStretch()
            self._info_layout.addLayout(browse_layout)

    def _add_installation_selector(self):
        """Add a combo box to select from multiple Blender installations."""
        selector_layout = QHBoxLayout()

        colors = _get_semantic_colors()
        selector_label = QLabel("<small>Other installations:</small>")
        selector_label.setStyleSheet(f"color: {colors['muted']};")
        selector_layout.addWidget(selector_label)

        self._installation_combo = QComboBox()
        self._installation_combo.setMaximumWidth(300)

        for info in self._all_installations:
            label = f"Blender {info.version_string}"
            if info.has_kotorblender:
                label += f" (kotorblender {info.kotorblender_version})"
            label += f" - {info.executable.parent.name}"
            self._installation_combo.addItem(label)

        # Select the current one
        for i, info in enumerate(self._all_installations):
            if info.executable == self._blender_info.executable:
                self._installation_combo.setCurrentIndex(i)
                break

        self._installation_combo.currentIndexChanged.connect(self._on_installation_changed)
        selector_layout.addWidget(self._installation_combo)
        selector_layout.addStretch()

        self._info_layout.addLayout(selector_layout)

    def _on_installation_changed(self, index: int):
        """Handle selection of a different Blender installation."""
        if 0 <= index < len(self._all_installations):
            self._blender_info = self._all_installations[index]
            self._update_blender_info_display()
            self._update_blender_button_state()

    def _update_blender_button_state(self):
        """Update the Blender button enabled state and tooltip."""
        is_enabled = self._blender_info.is_valid and self._blender_info.has_kotorblender
        self.ui.blenderButton.setEnabled(is_enabled)

        if self._blender_info.has_kotorblender:
            tooltip = "Use Blender for professional-grade 3D editing with full kotorblender support.\nBetter performance, more features, industry-standard tools."
        elif self._blender_info.is_valid:
            tooltip = "kotorblender is required to use Blender.\nClick 'Install kotorblender' above to install it."
        else:
            tooltip = "Blender is not installed or not found.\nClick 'Browse for Blender...' above to locate it."
        self.ui.blenderButton.setToolTip(tooltip)

    def _choose_blender(self):
        """User chose Blender."""
        self._choice = "blender"
        self.accept()

    def _choose_builtin(self):
        """User chose built-in editor."""
        self._choice = "builtin"
        self.accept()

    def _browse_blender(self):
        """Browse for Blender executable."""
        system = platform.system()

        if system == "Windows":
            file_filter = "Blender Executable (blender.exe);;All Files (*)"
            start_dir = "C:\\Program Files\\Blender Foundation"
        elif system == "Darwin":
            file_filter = "Blender Application (*.app);;All Files (*)"
            start_dir = "/Applications"
        else:
            file_filter = "Blender Executable (blender);;All Files (*)"
            start_dir = "/usr/bin"

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Blender Executable",
            start_dir,
            file_filter,
        )

        if path:
            # Try to detect this Blender
            new_info = detect_blender(path)
            if new_info.is_valid:
                self._blender_info = new_info
                self._update_blender_info_display()
                self._update_blender_button_state()
            else:
                QMessageBox.warning(
                    self,
                    "Invalid Blender",
                    f"Could not detect valid Blender at:\n{path}\n\n{new_info.error}",
                )

    def _browse_kotorblender(self):
        """Browse for kotorblender source folder."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select kotorblender folder (io_scene_kotor)",
            "",
            QFileDialog.Option.ShowDirsOnly,
        )

        if folder:
            folder_path = Path(folder)
            # Verify it's a valid kotorblender source
            if (folder_path / "__init__.py").is_file():
                self._install_kotorblender(source_path=folder_path)
            else:
                QMessageBox.warning(
                    self,
                    "Invalid kotorblender folder",
                    f"The selected folder does not appear to be a valid kotorblender source.\n\n"
                    f"Expected to find __init__.py in:\n{folder}\n\n"
                    f"Please select the 'io_scene_kotor' folder from the kotorblender download.",
                )

    def _install_kotorblender(self, source_path: Path | None = None):
        """Install kotorblender addon."""
        # Disable button during installation
        if self._install_button:
            self._install_button.setEnabled(False)
            self._install_button.setText("Installing...")

        try:
            # Try to verify IPC connection if Blender might be running
            # This ensures the addon is actually working, not just copied
            success, message = install_kotorblender(self._blender_info, source_path, verify_ipc=True)

            if success:
                # Update UI
                self._update_blender_info_display()
                self._update_blender_button_state()

                QMessageBox.information(
                    self,
                    "Installation Successful",
                    message,
                )
            else:
                QMessageBox.warning(
                    self,
                    "Installation Failed",
                    message,
                )
                # Re-enable button
                if self._install_button:
                    self._install_button.setEnabled(True)
                    self._install_button.setText("Install kotorblender")

        except Exception as e:
            QMessageBox.critical(
                self,
                "Installation Error",
                f"An error occurred while installing kotorblender:\n\n{e!s}",
            )
            # Re-enable button
            if self._install_button:
                self._install_button.setEnabled(True)
                self._install_button.setText("Install kotorblender")


def show_blender_choice_dialog(
    parent: QWidget | None = None,
    context: str = "Module Designer",
) -> tuple[str, bool]:
    """Show the Blender choice dialog and return the user's selection.

    Args:
        parent: Parent widget
        context: Context name for the dialog (e.g., "Module Designer", "GIT Editor")

    Returns:
        Tuple of (choice, remember) where choice is "blender" or "builtin",
        and remember is True if user wants to save the preference.
        Returns ("cancelled", False) if dialog was cancelled.
    """
    settings = get_blender_settings()

    # Check if user has a remembered preference
    if settings.remember_choice:
        return ("blender" if settings.prefer_blender else "builtin", True)

    # Check if Blender is available
    blender_info = settings.get_blender_info()

    # Always show dialog if Blender is detected (even without kotorblender)
    # This allows user to see the option and install kotorblender if needed
    if not blender_info.is_valid:
        # No Blender available, use built-in without showing dialog
        return ("builtin", False)

    # Show dialog (will inform user if kotorblender is missing)
    dialog = BlenderChoiceDialog(parent, blender_info, context)
    result = dialog.exec()

    if result == QDialog.DialogCode.Accepted:
        # Update settings if user wants to remember
        if dialog.remember_choice:
            settings.remember_choice = True
            settings.prefer_blender = dialog.choice == "blender"

        return (dialog.choice, dialog.remember_choice)

    return ("cancelled", False)


class BlenderConnectionWidget(QFrame):
    """Widget showing Blender connection status.

    Can be added to status bar or toolbar of editors.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._connected: bool = False
        self._setup_ui()

    def _setup_ui(self):
        """Setup the widget UI."""
        from toolset.uic.qtpy.widgets.blender_connection_widget import Ui_Form

        self.ui = Ui_Form()
        self.ui.setupUi(self)

        # Connect signals
        self.ui.connectButton.clicked.connect(self._on_connect_clicked)

        # Store references for easier access
        self._indicator = self.ui.indicatorLabel
        self._status_label = self.ui.statusLabel
        self._connect_button = self.ui.connectButton

        # Set initial indicator color
        colors = _get_semantic_colors()
        self._indicator.setStyleSheet(f"color: {colors['error']};")  # Error color by default

    def set_connected(self, connected: bool):
        """Update connection status display."""
        self._connected = connected
        colors = _get_semantic_colors()

        if connected:
            self._indicator.setStyleSheet(f"color: {colors['success']};")
            self._status_label.setText("Connected to Blender")
            self._connect_button.setText("Disconnect")
        else:
            self._indicator.setStyleSheet(f"color: {colors['error']};")
            self._status_label.setText("Disconnected")
            self._connect_button.setText("Connect")

    def set_connecting(self):
        """Show connecting status."""
        colors = _get_semantic_colors()
        self._indicator.setStyleSheet(f"color: {colors['warning']};")
        self._status_label.setText("Connecting...")
        self._connect_button.setEnabled(False)

    def set_error(self, message: str):
        """Show error status."""
        colors = _get_semantic_colors()
        self._indicator.setStyleSheet(f"color: {colors['error']};")
        self._status_label.setText(f"Error: {message}")
        self._connect_button.setEnabled(True)
        self._connect_button.setText("Retry")

    def _on_connect_clicked(self):
        """Handle connect/disconnect button click."""
        # This will be connected to the controller by the parent window
        pass


class BlenderSettingsWidget(QFrame):
    """Widget for Blender integration settings.

    Can be added to the settings dialog.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._blender_info: BlenderInfo | None = None
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        """Setup the widget UI."""
        from toolset.uic.qtpy.widgets.settings.blender_settings import Ui_Form

        self.ui = Ui_Form()
        self.ui.setupUi(self)

        # Connect signals
        self.ui.pathEdit.textChanged.connect(self._on_path_changed)
        self.ui.browseButton.clicked.connect(self._browse_blender)
        self.ui.detectButton.clicked.connect(self._detect_blender)
        self.ui.installKotorblenderButton.clicked.connect(self._install_kotorblender)

        # Store references for easier access
        self._path_edit = self.ui.pathEdit
        self._status_label = self.ui.statusLabel
        self._install_kotorblender_btn = self.ui.installKotorblenderButton
        self._prefer_blender_cb = self.ui.preferBlenderCheckbox
        self._remember_cb = self.ui.rememberCheckbox
        self._port_spin = self.ui.portSpinBox

        # Update status
        self._update_status()

    def _load_settings(self):
        """Load current settings."""
        settings = get_blender_settings()

        self._path_edit.setText(settings.custom_path or "")
        self._prefer_blender_cb.setChecked(settings.prefer_blender)
        self._remember_cb.setChecked(settings.remember_choice)
        self._port_spin.setValue(settings.ipc_port)

    def save_settings(self):
        """Save settings to the settings object."""
        settings = get_blender_settings()

        settings.custom_path = self._path_edit.text()
        settings.prefer_blender = self._prefer_blender_cb.isChecked()
        settings.remember_choice = self._remember_cb.isChecked()
        settings.ipc_port = self._port_spin.value()

    def _on_path_changed(self):
        """Handle path text change."""
        self._update_status()

    def _browse_blender(self):
        """Browse for Blender executable."""
        system = platform.system()

        if system == "Windows":
            file_filter = "Blender Executable (blender.exe);;All Files (*)"
        elif system == "Darwin":
            file_filter = "Blender Application (*.app);;All Files (*)"
        else:
            file_filter = "Blender Executable (blender);;All Files (*)"

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Blender Executable",
            "",
            file_filter,
        )

        if path:
            self._path_edit.setText(path)
            self._update_status()

    def _detect_blender(self):
        """Auto-detect Blender installation."""
        self._path_edit.clear()
        self._update_status()

    def _update_status(self):
        """Update the status display."""
        custom_path = self._path_edit.text() or None
        self._blender_info = detect_blender(custom_path)
        colors = _get_semantic_colors()

        if self._blender_info.is_valid:
            status = f"<span style='color: {colors['success']};'>✓ Blender {self._blender_info.version_string} found</span>"

            if self._blender_info.has_kotorblender:
                status += f"<br><span style='color: {colors['success']};'>✓ kotorblender {self._blender_info.kotorblender_version} installed</span>"
                self._install_kotorblender_btn.setVisible(False)
            else:
                status += f"<br><span style='color: {colors['warning']};'>⚠ kotorblender not found</span>"
                self._install_kotorblender_btn.setVisible(True)

            status += f"<br><small>{self._blender_info.executable}</small>"
        else:
            status = f"<span style='color: {colors['error']};'>✗ {self._blender_info.error}</span>"
            self._install_kotorblender_btn.setVisible(False)

        self._status_label.setText(status)

    def _install_kotorblender(self):
        """Install kotorblender addon."""
        if not self._blender_info or not self._blender_info.is_valid:
            return

        self._install_kotorblender_btn.setEnabled(False)
        self._install_kotorblender_btn.setText("Installing...")

        try:
            # Try to verify IPC connection if Blender might be running
            success, message = install_kotorblender(self._blender_info, verify_ipc=True)

            if success:
                QMessageBox.information(self, "Installation Successful", message)
                self._update_status()
            else:
                QMessageBox.warning(self, "Installation Failed", message)

        except Exception as e:
            QMessageBox.critical(
                self,
                "Installation Error",
                f"An error occurred while installing kotorblender:\n\n{e!s}",
            )
        finally:
            self._install_kotorblender_btn.setEnabled(True)
            self._install_kotorblender_btn.setText("Install kotorblender")
