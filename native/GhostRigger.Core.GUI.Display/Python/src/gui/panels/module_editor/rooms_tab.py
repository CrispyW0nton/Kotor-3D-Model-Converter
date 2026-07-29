"""Rooms workflow tab."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class RoomsTab(QtWidgets.QWidget):
    actionRequested = QtCore.Signal(str)

    ACTIONS = (
        "Load LYT",
        "Add Room",
        "Remove Room",
        "Duplicate Room",
        "Connect Room Openings",
        "Set Opening Intent",
        "Audit Room Connections",
        "Save Layout",
        "Focus Selected Room",
        "Auto Arrange",
        "Snap Room to Grid",
    )
    ACTION_OBJECT_NAMES = {
        "Load LYT": "mapStudioRoomsLoadLytButton",
        "Add Room": "mapStudioRoomsAddRoomButton",
        "Remove Room": "mapStudioRoomsRemoveRoomButton",
        "Duplicate Room": "mapStudioRoomsDuplicateRoomButton",
        "Connect Room Openings": "mapStudioRoomsConnectOpeningsButton",
        "Set Opening Intent": "mapStudioRoomsOpeningIntentButton",
        "Audit Room Connections": "mapStudioRoomsAuditConnectionsButton",
        "Save Layout": "mapStudioRoomsSaveLayoutButton",
        "Focus Selected Room": "mapStudioRoomsFocusSelectedButton",
        "Auto Arrange": "mapStudioRoomsAutoArrangeButton",
        "Snap Room to Grid": "mapStudioRoomsSnapToGridButton",
    }
    PRIMARY_ACTIONS = (
        "Add Room",
        "Connect Room Openings",
        "Audit Room Connections",
        "Focus Selected Room",
    )
    ACTION_LABELS = {
        "Add Room": "Add / Import Room…",
        "Connect Room Openings": "Connect Selected Doorways",
        "Audit Room Connections": "Check Doorway Connections",
    }

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        # Workflow guidance lives in the tab tooltip, not panel body text —
        # dock space belongs to the actual controls.
        self.setToolTip(
            "Rooms workflow: load or author room layout, arrange room positions, then validate LYT/VIS links before packaging.\n"
            "LYT stores room models and transforms; VIS controls which rooms can see each other. "
            "Keep room resrefs stable for WOK, MDL/MDX, and placed resources.\n"
            "Use Builder for new geometry, then Rooms to place, duplicate, connect doorway openings, focus, snap, and save the layout.\n"
            "Connected openings align room geometry and create symmetric VIS intent. "
            "Set unused openings as available connectors, intentional module exits, or sealed authentic doors; "
            "WOK transitions still require export validation and a live warp test."
        )
        self.workflow_label = QtWidgets.QLabel(
            "Recommended: draw complete rooms on Build. Each room already owns its visible floor and WOK. "
            "Add a door, then drag the next room—or a compatible vanilla room—to the doorway magnet."
        )
        self.workflow_label.setObjectName("mapStudioRoomsWorkflowLabel")
        self.workflow_label.setWordWrap(True)
        self.workflow_label.setToolTip(self.toolTip())
        self.layout_label = QtWidgets.QLabel()
        self.layout_label.setObjectName("mapStudioRoomsLayoutHintLabel")
        self.layout_label.setWordWrap(True)
        self.layout_label.setText("Room connections: no authored floor-plan openings yet.")
        self.authoring_label = QtWidgets.QLabel()
        self.authoring_label.setObjectName("mapStudioRoomsAuthoringHintLabel")
        self.authoring_label.setVisible(False)
        layout.addWidget(self.workflow_label)
        primary_box = QtWidgets.QGroupBox("Room Assembly")
        primary_layout = QtWidgets.QVBoxLayout(primary_box)
        self.advanced_toggle = QtWidgets.QToolButton(self)
        self.advanced_toggle.setObjectName("mapStudioRoomsAdvancedToggle")
        self.advanced_toggle.setText("Layout file / advanced room tools")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setChecked(False)
        self.advanced_toggle.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        self.advanced_toggle.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.advanced_widget = QtWidgets.QWidget(self)
        self.advanced_widget.setObjectName("mapStudioRoomsAdvancedTools")
        advanced_layout = QtWidgets.QVBoxLayout(self.advanced_widget)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        for label in self.ACTIONS:
            button = QtWidgets.QPushButton(self.ACTION_LABELS.get(label, label))
            button.setObjectName(self.ACTION_OBJECT_NAMES.get(label, ""))
            button.clicked.connect(lambda _checked=False, text=label: self.actionRequested.emit(text))
            if label in self.PRIMARY_ACTIONS:
                primary_layout.addWidget(button)
            else:
                advanced_layout.addWidget(button)
        self.advanced_widget.setVisible(False)
        self.advanced_toggle.toggled.connect(self._set_advanced_visible)
        layout.addWidget(primary_box)
        layout.addWidget(self.advanced_toggle)
        layout.addWidget(self.advanced_widget)
        layout.addStretch(1)

    def _set_advanced_visible(self, visible: bool) -> None:
        self.advanced_widget.setVisible(bool(visible))
        self.advanced_toggle.setArrowType(
            QtCore.Qt.ArrowType.DownArrow if visible else QtCore.Qt.ArrowType.RightArrow
        )

    def set_connection_audit(self, audit: object) -> None:
        """Show room-opening connection health without implying game proof."""

        summary = str(getattr(audit, "summary", "") or "").strip()
        self.layout_label.setText(summary or "Room connections: not available.")
        warnings = tuple(getattr(audit, "warnings", ()) or ())
        tooltip = summary
        if warnings:
            tooltip = f"{tooltip}\n\n" + "\n".join(str(item) for item in warnings[:6])
        tooltip = (
            f"{tooltip}\n\nConnection health covers authored opening alignment and VIS intent. "
            "KOTOR WOK transition edges and in-game traversal remain separate export/game-proof gates."
        )
        self.layout_label.setToolTip(tooltip)
