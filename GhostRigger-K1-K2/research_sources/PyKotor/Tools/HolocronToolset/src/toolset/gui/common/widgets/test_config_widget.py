"""Test Configuration Widget - Configures event parameters for dry-run testing of NSS scripts."""

from __future__ import annotations

from typing import Any

from qtpy.QtWidgets import (
    QDialog,
    QWidget,
)

from toolset.gui.common.localization import translate as tr


class TestConfigWidget(QWidget):
    """Widget for configuring test parameters before running a script test."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._entry_point: str = "main"  # "main" or "StartingConditional"
        self._event_number: int = 1001  # Default: HEARTBEAT
        self._test_params: dict[str, Any] = {}
        self.setup_ui()

    def setup_ui(self):
        """Set up the UI components."""
        from toolset.uic.qtpy.widgets.test_config_widget import Ui_TestConfigWidget

        self.ui: Ui_TestConfigWidget = Ui_TestConfigWidget()
        self.ui.setupUi(self)

        # Populate event combo box
        self.ui.eventCombo.addItem("HEARTBEAT (1001)", 1001)
        self.ui.eventCombo.addItem("PERCEIVE (1002)", 1002)
        self.ui.eventCombo.addItem("END OF COMBAT (1003)", 1003)
        self.ui.eventCombo.addItem("ON DIALOGUE (1004)", 1004)
        self.ui.eventCombo.addItem("ATTACKED (1005)", 1005)
        self.ui.eventCombo.addItem("DAMAGED (1006)", 1006)
        self.ui.eventCombo.addItem("DEATH (1007)", 1007)
        self.ui.eventCombo.addItem("DISTURBED (1008)", 1008)
        self.ui.eventCombo.addItem("BLOCKED (1009)", 1009)
        self.ui.eventCombo.addItem("SPELL CAST AT (1010)", 1010)
        self.ui.eventCombo.addItem("DIALOGUE END (1011)", 1011)
        self.ui.eventCombo.addItem("Custom...", -1)

        # Set placeholder texts with localization
        self.ui.lastAttackerEdit.setPlaceholderText(tr("OBJECT_INVALID (default: 0)"))
        self.ui.lastPerceivedEdit.setPlaceholderText(tr("OBJECT_INVALID (default: 0)"))
        self.ui.eventCreatorEdit.setPlaceholderText(tr("OBJECT_SELF (default: 1)"))
        self.ui.eventTargetEdit.setPlaceholderText(tr("OBJECT_SELF (default: 1)"))

        # Connect signals
        self.ui.eventCombo.currentIndexChanged.connect(self._on_event_changed)
        self.ui.customEventSpin.valueChanged.connect(self._update_event_number)

    def _on_event_changed(self, index: int):
        """Handle event combo box change."""
        custom_enabled = self.ui.eventCombo.itemData(index) == -1
        self.ui.customEventSpin.setEnabled(custom_enabled)
        if not custom_enabled:
            event_data = self.ui.eventCombo.itemData(index)
            if event_data is not None:
                self._event_number = int(event_data)
        else:
            self._event_number = self.ui.customEventSpin.value()

    def _update_event_number(self, value: int):
        """Update event number from custom spinbox."""
        if self.ui.eventCombo.currentData() == -1:
            self._event_number = value

    def set_entry_point(self, entry_point: str):
        """Set the detected entry point type.

        Args:
        ----
            entry_point: str: "main" or "StartingConditional"
        """
        self._entry_point = entry_point
        if entry_point == "StartingConditional":
            self.ui.entryPointLabel.setText(tr("Entry Point: StartingConditional()"))
            # Hide event configuration for StartingConditional
            self.ui.eventCombo.setEnabled(False)
            self.ui.customEventSpin.setEnabled(False)
        else:
            self.ui.entryPointLabel.setText(tr("Entry Point: main()"))
            self.ui.eventCombo.setEnabled(True)

    def get_test_config(self) -> dict[str, Any]:
        """Get the test configuration.

        Returns:
        -------
            dict: Test configuration with event_number and mock values
        """
        config: dict[str, Any] = {"entry_point": self._entry_point, "event_number": self._event_number, "mocks": {}}

        # Parse mock values - create proper mock functions
        # NOTE: Lambdas need to capture values, so we use default args to avoid closure issues
        try:
            attacker_val = int(self.ui.lastAttackerEdit.text() or "0")
            config["mocks"]["GetLastAttacker"] = lambda o=1, val=attacker_val: val
        except ValueError:
            # Default to OBJECT_INVALID
            config["mocks"]["GetLastAttacker"] = lambda o=1: 0

        try:
            perceived_val = int(self.ui.lastPerceivedEdit.text() or "0")
            config["mocks"]["GetLastPerceived"] = lambda val=perceived_val: val
        except ValueError:
            # Default to OBJECT_INVALID
            config["mocks"]["GetLastPerceived"] = lambda: 0

        try:
            creator_val = int(self.ui.eventCreatorEdit.text() or "1")
            config["mocks"]["GetEventCreator"] = lambda val=creator_val: val
        except ValueError:
            # Default to OBJECT_SELF
            config["mocks"]["GetEventCreator"] = lambda: 1

        try:
            target_val = int(self.ui.eventTargetEdit.text() or "1")
            config["mocks"]["GetEventTarget"] = lambda val=target_val: val
        except ValueError:
            # Default to OBJECT_SELF
            config["mocks"]["GetEventTarget"] = lambda: 1

        # Always mock GetUserDefinedEventNumber to return the selected event
        event_num = self._event_number
        config["mocks"]["GetUserDefinedEventNumber"] = lambda val=event_num: val

        return config


class TestConfigDialog(QDialog):
    """Dialog for configuring test run parameters."""

    def __init__(self, entry_point: str = "main", parent: QWidget | None = None):
        super().__init__(parent)

        # Load UI from .ui file
        from toolset.uic.qtpy.dialogs.test_config import Ui_Dialog

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        self.setWindowTitle(tr("Configure Test Run"))

        # Populate event combo box
        self.ui.eventCombo.addItem("HEARTBEAT (1001)", 1001)
        self.ui.eventCombo.addItem("PERCEIVE (1002)", 1002)
        self.ui.eventCombo.addItem("END OF COMBAT (1003)", 1003)
        self.ui.eventCombo.addItem("ON DIALOGUE (1004)", 1004)
        self.ui.eventCombo.addItem("ATTACKED (1005)", 1005)
        self.ui.eventCombo.addItem("DAMAGED (1006)", 1006)
        self.ui.eventCombo.addItem("DEATH (1007)", 1007)
        self.ui.eventCombo.addItem("DISTURBED (1008)", 1008)
        self.ui.eventCombo.addItem("BLOCKED (1009)", 1009)
        self.ui.eventCombo.addItem("SPELL CAST AT (1010)", 1010)
        self.ui.eventCombo.addItem("DIALOGUE END (1011)", 1011)
        self.ui.eventCombo.addItem("Custom...", -1)

        # Connect signals
        self.ui.eventCombo.currentIndexChanged.connect(self._on_event_changed)
        self.ui.customEventSpin.valueChanged.connect(self._update_event_number)
        self.ui.buttonBox.accepted.connect(self.accept)
        self.ui.buttonBox.rejected.connect(self.reject)

        # Set entry point
        self._entry_point: str = entry_point
        self._event_number: int = 1001
        self.set_entry_point(entry_point)

    def _on_event_changed(self, index: int):
        """Handle event combo box change."""
        custom_enabled = self.ui.eventCombo.itemData(index) == -1
        self.ui.customEventSpin.setEnabled(custom_enabled)
        if not custom_enabled:
            event_data = self.ui.eventCombo.itemData(index)
            if event_data is not None:
                self._event_number = int(event_data)
        else:
            self._event_number = self.ui.customEventSpin.value()

    def _update_event_number(self, value: int):
        """Update event number from custom spinbox."""
        if self.ui.eventCombo.currentData() == -1:
            self._event_number = value

    def set_entry_point(self, entry_point: str):
        """Set the detected entry point type.

        Args:
        ----
            entry_point: str: "main" or "StartingConditional"
        """
        self._entry_point = entry_point
        if entry_point == "StartingConditional":
            self.ui.entryPointLabel.setText(tr("Entry Point: StartingConditional()"))
            # Hide event configuration for StartingConditional
            self.ui.eventCombo.setEnabled(False)
            self.ui.customEventSpin.setEnabled(False)
        else:
            self.ui.entryPointLabel.setText(tr("Entry Point: main()"))
            self.ui.eventCombo.setEnabled(True)

    def get_test_config(self) -> dict[str, Any]:
        """Get the test configuration.

        Returns:
        -------
            dict: Test configuration with event_number and mock values
        """
        config: dict[str, Any] = {"entry_point": self._entry_point, "event_number": self._event_number, "mocks": {}}

        # Parse mock values - create proper mock functions
        # NOTE: Lambdas need to capture values, so we use default args to avoid closure issues
        try:
            attacker_val = int(self.ui.lastAttackerEdit.text() or "0")
            config["mocks"]["GetLastAttacker"] = lambda o=1, val=attacker_val: val
        except ValueError:
            # Default to OBJECT_INVALID
            config["mocks"]["GetLastAttacker"] = lambda o=1: 0

        try:
            perceived_val = int(self.ui.lastPerceivedEdit.text() or "0")
            config["mocks"]["GetLastPerceived"] = lambda val=perceived_val: val
        except ValueError:
            # Default to OBJECT_INVALID
            config["mocks"]["GetLastPerceived"] = lambda: 0

        try:
            creator_val = int(self.ui.eventCreatorEdit.text() or "1")
            config["mocks"]["GetEventCreator"] = lambda val=creator_val: val
        except ValueError:
            # Default to OBJECT_SELF
            config["mocks"]["GetEventCreator"] = lambda: 1

        try:
            target_val = int(self.ui.eventTargetEdit.text() or "1")
            config["mocks"]["GetEventTarget"] = lambda val=target_val: val
        except ValueError:
            # Default to OBJECT_SELF
            config["mocks"]["GetEventTarget"] = lambda: 1

        # Always mock GetUserDefinedEventNumber to return the selected event
        event_num = self._event_number
        config["mocks"]["GetUserDefinedEventNumber"] = lambda val=event_num: val

        return config
