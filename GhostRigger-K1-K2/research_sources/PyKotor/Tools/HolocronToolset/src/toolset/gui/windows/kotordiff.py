"""KotorDiff integration window for the Holocron Toolset."""

from __future__ import annotations

import os
import sys
import traceback

from pathlib import Path
from typing import TYPE_CHECKING

from qtpy import QtCore
from qtpy.QtCore import QSettings, QThread
from qtpy.QtGui import QTextCursor
from qtpy.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QMainWindow,
    QMessageBox,
)

from pykotor.diff_tool.app import DiffConfig, run_application
from pykotor.extract.installation import Installation

if TYPE_CHECKING:
    from qtpy.QtWidgets import (
        QLineEdit,
        QWidget,
    )

    from toolset.data.installation import HTInstallation


class KotorDiffThread(QThread):
    """Thread to run KotorDiff operations without blocking the UI."""

    output_signal = QtCore.Signal(str)  # pyright: ignore[reportPrivateImportUsage]
    finished_signal = QtCore.Signal(int)  # pyright: ignore[reportPrivateImportUsage]

    def __init__(self, config: DiffConfig):
        super().__init__()
        self.config = config

    def run(self):
        """Execute KotorDiff in a separate thread."""
        try:
            # Redirect output to our signal
            original_stdout = sys.stdout
            original_stderr = sys.stderr

            class OutputRedirector:
                def __init__(self, signal):
                    self.signal = signal

                def write(self, text):
                    if text.strip():
                        self.signal.emit(text)

                def flush(self):
                    pass

            sys.stdout = OutputRedirector(self.output_signal)
            sys.stderr = OutputRedirector(self.output_signal)

            # Run KotorDiff with the config object
            exit_code = run_application(self.config)

            # Restore stdout/stderr
            sys.stdout = original_stdout
            sys.stderr = original_stderr

            self.finished_signal.emit(exit_code)
        except Exception as e:  # noqa: BLE001
            self.output_signal.emit(f"Error: {e.__class__.__name__}: {e}{os.linesep}{traceback.format_exc()}")
            self.finished_signal.emit(1)


class KotorDiffWindow(QMainWindow):
    """Window for running KotorDiff operations."""

    def __init__(
        self,
        parent: QWidget | None = None,
        installations: dict[str, HTInstallation] | None = None,
        active_installation: HTInstallation | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Kotor Diff - Holocron Toolset")
        self.resize(900, 700)

        self._diff_thread: KotorDiffThread | None = None
        self._installations: dict[str, HTInstallation] = installations or {}
        self._active_installation: HTInstallation | None = active_installation
        from toolset.utils.misc import get_qsettings_organization

        self._settings = QSettings(get_qsettings_organization("HolocronToolset"), "KotorDiff")
        self._setup_ui()
        self._load_settings()

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

    def _setup_ui(self):
        """Set up the user interface."""
        from toolset.uic.qtpy.windows.kotordiff import Ui_MainWindow

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Set up path selectors
        self._setup_path_selector(1, is_first=True)
        self._setup_path_selector(2, is_first=False)

        # Set up TSLPatchData placeholder text
        from toolset.gui.common.localization import translate as tr

        self.ui.tslpatchdataEdit.setPlaceholderText(tr("Path to tslpatchdata folder"))

        # Connect TSLPatchData checkbox signals
        self.ui.tslpatchdataCheck.toggled.connect(self.ui.tslpatchdataEdit.setEnabled)
        self.ui.tslpatchdataCheck.toggled.connect(self.ui.tslpatchdataBrowseBtn.setEnabled)
        self.ui.tslpatchdataCheck.toggled.connect(self.ui.iniNameEdit.setEnabled)
        self.ui.tslpatchdataBrowseBtn.clicked.connect(lambda: self._browse_directory(self.ui.tslpatchdataEdit))

        # Connect button signals
        self.ui.runBtn.clicked.connect(self._run_diff)
        self.ui.clearBtn.clicked.connect(self.ui.outputText.clear)

        # QPushButton.clicked emits a bool; QWidget.close takes no args.
        def _close_window(*_):
            self.close()

        self.ui.closeBtn.clicked.connect(_close_window)

    def _setup_path_selector(
        self,
        path_num: int,
        is_first: bool,  # noqa: FBT001
    ):
        """Set up a path selector with installation combobox and custom path options."""
        # Get UI widgets
        installation_radio = getattr(self.ui, f"path{path_num}InstallationRadio")
        custom_radio = getattr(self.ui, f"path{path_num}CustomRadio")
        installation_combo = getattr(self.ui, f"path{path_num}Combo")
        path_edit = getattr(self.ui, f"path{path_num}Edit")
        browse_btn = getattr(self.ui, f"path{path_num}Browse")

        # Create a button group to ensure these radio buttons are mutually exclusive per path
        button_group = QButtonGroup(self)
        button_group.addButton(installation_radio)
        button_group.addButton(custom_radio)

        # Store button group for later access
        setattr(self, f"_path{path_num}_button_group", button_group)

        # Populate installation combobox
        for name, installation in self._installations.items():
            installation_combo.addItem(name, installation)

        # Set current installation as default for path 1
        if is_first and self._active_installation:
            idx = installation_combo.findData(self._active_installation)
            if idx >= 0:
                installation_combo.setCurrentIndex(idx)

        # Connect radio buttons
        installation_radio.toggled.connect(installation_combo.setEnabled)
        installation_radio.toggled.connect(lambda checked: path_edit.setDisabled(checked))
        installation_radio.toggled.connect(lambda checked: browse_btn.setDisabled(checked))

        # Default to installation mode if we have installations
        if self._installations:
            installation_radio.setChecked(True)
            path_edit.setEnabled(False)
            browse_btn.setEnabled(False)
        else:
            custom_radio.setChecked(True)
            installation_combo.setEnabled(False)

        # Connect browse button
        browse_btn.clicked.connect(lambda: self._browse_path(path_edit))

    def _get_path_value(self, path_num: int) -> str | None:
        """Get the path value for the given path number."""
        installation_radio = getattr(self.ui, f"path{path_num}InstallationRadio")
        combo = getattr(self.ui, f"path{path_num}Combo")
        edit = getattr(self.ui, f"path{path_num}Edit")

        if installation_radio.isChecked():
            # Check if it's a custom text entry or a real installation
            text = combo.currentText().strip()
            if not text:
                return None
            installation = combo.currentData()
            if installation is None:
                # User typed in a custom path
                return text
            return str(installation.path())
        text = edit.text().strip()
        return text if text else None

    def _browse_path(self, line_edit: "QLineEdit"):
        """Browse for a file or directory."""
        path = QFileDialog.getExistingDirectory(self, "Select Directory")
        if not path:
            path = QFileDialog.getOpenFileName(self, "Select File")[0]
        if path:
            line_edit.setText(path)

    def _browse_directory(self, line_edit: "QLineEdit | None" = None):
        """Browse for a directory."""
        if line_edit is None:
            line_edit = self.ui.tslpatchdataEdit
        path = QFileDialog.getExistingDirectory(self, "Select Directory")
        if path:
            line_edit.setText(path)

    def _load_settings(self):
        """Load saved settings from QSettings."""
        # Load path selections
        for path_num in [1, 2]:
            use_installation = self._settings.value(f"path{path_num}_use_installation", True, type=bool)
            installation_name = self._settings.value(f"path{path_num}_installation", "")
            custom_path = self._settings.value(f"path{path_num}_custom", "")

            installation_radio = getattr(self.ui, f"path{path_num}InstallationRadio")
            custom_radio = getattr(self.ui, f"path{path_num}CustomRadio")
            combo = getattr(self.ui, f"path{path_num}Combo")
            edit = getattr(self.ui, f"path{path_num}Edit")

            if use_installation:
                installation_radio.setChecked(True)
                idx = combo.findText(installation_name) if installation_name else -1
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                elif installation_name:
                    combo.setCurrentText(installation_name)
            else:
                custom_radio.setChecked(True)
                edit.setText(custom_path)

        # Load options
        self.ui.compareHashesCheck.setChecked(self._settings.value("compare_hashes", True, type=bool))
        self.ui.tslpatchdataCheck.setChecked(self._settings.value("tslpatchdata_enabled", False, type=bool))
        self.ui.tslpatchdataEdit.setText(self._settings.value("tslpatchdata_path", ""))
        self.ui.iniNameEdit.setText(self._settings.value("ini_filename", "changes.ini"))
        self.ui.logLevelCombo.setCurrentText(self._settings.value("log_level", "info"))

    def _save_settings(self):
        """Save current settings to QSettings."""
        # Save path selections
        for path_num in [1, 2]:
            installation_radio = getattr(self.ui, f"path{path_num}InstallationRadio")
            combo = getattr(self.ui, f"path{path_num}Combo")
            edit = getattr(self.ui, f"path{path_num}Edit")

            self._settings.setValue(f"path{path_num}_use_installation", installation_radio.isChecked())
            self._settings.setValue(f"path{path_num}_installation", combo.currentText())
            self._settings.setValue(f"path{path_num}_custom", edit.text())

        # Save options
        self._settings.setValue("compare_hashes", self.ui.compareHashesCheck.isChecked())
        self._settings.setValue("tslpatchdata_enabled", self.ui.tslpatchdataCheck.isChecked())
        self._settings.setValue("tslpatchdata_path", self.ui.tslpatchdataEdit.text())
        self._settings.setValue("ini_filename", self.ui.iniNameEdit.text())
        self._settings.setValue("log_level", self.ui.logLevelCombo.currentText())

    def closeEvent(self, event):  # noqa: N802
        """Handle window close event."""
        self._save_settings()
        super().closeEvent(event)

    def _run_diff(self):
        """Run the KotorDiff operation."""
        # Save settings before running
        self._save_settings()

        # Validate inputs
        path1_str = self._get_path_value(1)
        path2_str = self._get_path_value(2)

        if not path1_str or not path2_str:
            QMessageBox.warning(self, "Invalid Input", "Please provide both Path 1 and Path 2.")
            return

        # Disable run button during execution
        self.ui.runBtn.setEnabled(False)
        self.ui.outputText.clear()
        self.ui.outputText.append("Starting KotorDiff...\n")

        # Convert string paths to Path/Installation objects
        paths: list[Path | Installation] = []
        for path_str in [path1_str, path2_str]:
            path_obj = Path(path_str)
            try:
                # Try to create an Installation object
                installation = Installation(path_obj)
                paths.append(installation)
            except Exception:  # noqa: BLE001
                # Fall back to Path object
                paths.append(path_obj)

        # Build configuration
        config = DiffConfig(
            paths=paths,
            tslpatchdata_path=(Path(self.ui.tslpatchdataEdit.text().strip()) if self.ui.tslpatchdataCheck.isChecked() and self.ui.tslpatchdataEdit.text().strip() else None),
            ini_filename=(self.ui.iniNameEdit.text().strip() or "changes.ini"),
            output_log_path=None,
            log_level=self.ui.logLevelCombo.currentText(),
            output_mode="quiet",
            use_colors=False,
            compare_hashes=self.ui.compareHashesCheck.isChecked(),
            use_profiler=False,
            filters=None,
            logging_enabled=True,
        )

        # Run in thread
        self._diff_thread = KotorDiffThread(config)
        self._diff_thread.output_signal.connect(self._append_output)
        self._diff_thread.finished_signal.connect(self._diff_finished)
        self._diff_thread.start()

    def _append_output(self, text: str):
        """Append text to the output area."""
        cursor = self.ui.outputText.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.ui.outputText.setTextCursor(cursor)
        # Ensure the view scrolls to the bottom
        self.ui.outputText.ensureCursorVisible()

    def _diff_finished(self, exit_code: int):
        """Handle diff completion."""
        self.ui.runBtn.setEnabled(True)

        if exit_code == 0:
            self.ui.outputText.append("\n\nDiff completed successfully!")
            QMessageBox.information(self, "Success", "Diff completed successfully!")
        else:
            self.ui.outputText.append(f"\n\nDiff completed with exit code: {exit_code}")
            QMessageBox.warning(self, "Completed", f"Diff completed with exit code: {exit_code}")
