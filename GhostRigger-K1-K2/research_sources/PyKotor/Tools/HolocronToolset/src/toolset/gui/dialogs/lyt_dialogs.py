"""Dialog windows for LYT editing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtWidgets import QDialog, QMessageBox

from utility.common.geometry import Vector3

if TYPE_CHECKING:
    from pykotor.resource.formats.lyt.lyt_data import LYTDoorHook, LYTObstacle, LYTRoom, LYTTrack


class RoomPropertiesDialog(QDialog):
    def __init__(self, room: LYTRoom, parent=None):
        super().__init__(parent)
        self.room = room
        from toolset.gui.common.localization import translate as tr

        # Load UI from .ui file
        from toolset.uic.qtpy.dialogs.room_properties import Ui_Dialog

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        self.setWindowTitle(tr("Room Properties"))

        # Set initial values
        self.ui.modelInput.setText(self.room.model)
        self.ui.xSpin.setValue(self.room.position.x)
        self.ui.ySpin.setValue(self.room.position.y)
        self.ui.zSpin.setValue(self.room.position.z)

        # Connect buttons (connections are already set up in .ui file, but we can also do it here for clarity)
        self.ui.okButton.clicked.connect(lambda: self.accept())
        self.ui.cancelButton.clicked.connect(lambda: self.reject())

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

    def accept(self):
        try:
            # Validate inputs
            model = self.ui.modelInput.text().strip()
            from toolset.gui.common.localization import translate as tr, trf

            if not model:
                QMessageBox.warning(self, tr("Invalid Input"), tr("Model name cannot be empty."))
                return

            # Update room properties
            self.room.model = model
            self.room.position = Vector3(self.ui.xSpin.value(), self.ui.ySpin.value(), self.ui.zSpin.value())
            super().accept()
        except Exception as e:
            QMessageBox.critical(self, tr("Error"), trf("Failed to update room properties: {error}", error=str(e)))


class TrackPropertiesDialog(QDialog):
    def __init__(self, rooms: list[LYTRoom], track: LYTTrack, parent=None):
        super().__init__(parent)
        self.track = track
        self.rooms = rooms
        from toolset.gui.common.localization import translate as tr

        # Load UI from .ui file
        from toolset.uic.qtpy.dialogs.track_properties import Ui_Dialog

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        self.setWindowTitle(tr("Track Properties"))

        # Set initial values
        self.ui.modelInput.setText(self.track.model)
        self.ui.xSpin.setValue(self.track.position.x)
        self.ui.ySpin.setValue(self.track.position.y)
        self.ui.zSpin.setValue(self.track.position.z)

        # Connect buttons (connections are already set up in .ui file, but we can also do it here for clarity)
        self.ui.okButton.clicked.connect(lambda: self.accept())
        self.ui.cancelButton.clicked.connect(lambda: self.reject())

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

    def accept(self):
        try:
            # Validate inputs
            model = self.ui.modelInput.text().strip()
            from toolset.gui.common.localization import translate as tr, trf

            if not model:
                QMessageBox.warning(self, tr("Invalid Input"), tr("Model name cannot be empty."))
                return

            # Update track properties
            self.track.model = model
            self.track.position = Vector3(self.ui.xSpin.value(), self.ui.ySpin.value(), self.ui.zSpin.value())
            super().accept()
        except Exception as e:
            from toolset.gui.common.localization import translate as tr, trf

            QMessageBox.critical(self, tr("Error"), trf("Failed to update track properties: {error}", error=str(e)))


class ObstaclePropertiesDialog(QDialog):
    def __init__(self, obstacle: LYTObstacle, parent=None):
        super().__init__(parent)
        self.obstacle = obstacle
        from toolset.gui.common.localization import translate as tr

        # Load UI from .ui file
        from toolset.uic.qtpy.dialogs.obstacle_properties import Ui_Dialog

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        self.setWindowTitle(tr("Obstacle Properties"))

        # Set initial values
        self.ui.modelInput.setText(self.obstacle.model)
        self.ui.xSpin.setValue(self.obstacle.position.x)
        self.ui.ySpin.setValue(self.obstacle.position.y)
        self.ui.zSpin.setValue(self.obstacle.position.z)

        # Connect buttons (connections are already set up in .ui file, but we can also do it here for clarity)
        self.ui.okButton.clicked.connect(lambda: self.accept())
        self.ui.cancelButton.clicked.connect(lambda: self.reject())

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

    def accept(self):
        try:
            # Validate inputs
            model = self.ui.modelInput.text().strip()
            from toolset.gui.common.localization import translate as tr, trf

            if not model:
                QMessageBox.warning(self, tr("Invalid Input"), tr("Model name cannot be empty."))
                return

            # Update obstacle properties
            self.obstacle.model = model
            self.obstacle.position = Vector3(self.ui.xSpin.value(), self.ui.ySpin.value(), self.ui.zSpin.value())
            super().accept()
        except Exception as e:
            from toolset.gui.common.localization import translate as tr, trf

            QMessageBox.critical(self, tr("Error"), trf("Failed to update obstacle properties: {error}", error=str(e)))


class DoorHookPropertiesDialog(QDialog):
    def __init__(self, doorhook: LYTDoorHook, parent=None):
        super().__init__(parent)
        self.doorhook: LYTDoorHook = doorhook
        from toolset.gui.common.localization import translate as tr

        # Load UI from .ui file
        from toolset.uic.qtpy.dialogs.door_hook_properties import Ui_Dialog

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        self.setWindowTitle(tr("Door Hook Properties"))

        # Set initial values
        self.ui.roomInput.setText(self.doorhook.room)
        self.ui.doorInput.setText(self.doorhook.door)
        self.ui.xSpin.setValue(self.doorhook.position.x)
        self.ui.ySpin.setValue(self.doorhook.position.y)
        self.ui.zSpin.setValue(self.doorhook.position.z)

        # Connect buttons (connections are already set up in .ui file, but we can also do it here for clarity)
        self.ui.okButton.clicked.connect(lambda: self.accept())
        self.ui.cancelButton.clicked.connect(lambda: self.reject())

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

    def accept(self):
        try:
            # Validate inputs
            from toolset.gui.common.localization import translate as tr, trf

            room = self.ui.roomInput.text().strip()
            door = self.ui.doorInput.text().strip()
            if not room or not door:
                QMessageBox.warning(self, tr("Invalid Input"), tr("Room and door names cannot be empty."))
                return

            # Update doorhook properties
            self.doorhook.room = room
            self.doorhook.door = door
            self.doorhook.position = Vector3(self.ui.xSpin.value(), self.ui.ySpin.value(), self.ui.zSpin.value())
            super().accept()
        except Exception as e:
            from toolset.gui.common.localization import translate as tr, trf

            QMessageBox.critical(self, tr("Error"), trf("Failed to update door hook properties: {error}", error=str(e)))


class AddRoomDialog(QDialog):
    """Dialog for adding a new room to the LYT."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

    def _setup_ui(self):
        """Initialize the UI."""
        from toolset.gui.common.localization import translate as tr
        from toolset.uic.qtpy.dialogs.add_room import Ui_Dialog

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        self.setWindowTitle(tr("Add Room"))

        # Connect buttons
        self.ui.buttonBox.accepted.connect(self.accept)
        self.ui.buttonBox.rejected.connect(self.reject)


class AddDoorHookDialog(QDialog):
    """Dialog for adding a new door hook."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

    def _setup_ui(self):
        """Initialize the UI."""
        from toolset.gui.common.localization import translate as tr
        from toolset.uic.qtpy.dialogs.add_door_hook import Ui_Dialog

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        self.setWindowTitle(tr("Add Door Hook"))

        # Connect buttons
        self.ui.okButton.clicked.connect(lambda: self.accept())
        self.ui.cancelButton.clicked.connect(lambda: self.reject())
