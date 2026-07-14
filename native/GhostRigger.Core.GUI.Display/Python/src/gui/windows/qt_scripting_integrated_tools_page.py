"""Navigation surface for GhostStudio systems that supersede legacy editors."""

from __future__ import annotations

from typing import Any, Optional

from PySide6 import QtCore, QtWidgets


class QtScriptingIntegratedToolsPage(QtWidgets.QWidget):
    """Keep the scripting suite uncluttered while preserving adjacent tools."""

    routeRequested = QtCore.Signal(str)

    _ROUTES = (
        ("resource_browser", "Resource Browser", "Search game, module, Override, and project resources."),
        ("blueprint_page", "Blueprint & GFF Authoring", "Open the suite's typed, loss-preserving editor for UTC, UTP, UTD, UTI, UTE, UTM, UTS, UTT, UTW, and other GFF resources."),
        ("map_studio", "Map Studio", "Place and edit GIT creatures, doors, placeables, triggers, sounds, waypoints, and module content."),
        ("output_log", "Output Log", "Review compiler, validation, packaging, IPC, and runtime diagnostics."),
        ("settings", "Game Libraries & Preferences", "Configure K1/K2 installations, shared themes, layouts, and application preferences."),
        ("tutorial_page", "Scripting Guides", "Open task-based scripting, dialogue, quest, data, package, and migration walkthroughs."),
        ("tutorial", "All GhostStudio Tutorials", "Open the shared guided-learning workspace for the full application."),
    )

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("scriptingStudioIntegratedToolsPage")
        self.setProperty("ghostLayoutId", "scriptingStudioIntegratedTools")
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(10)
        title = QtWidgets.QLabel("Integrated GhostStudio Tools", self)
        title.setProperty("headingLevel", 1)
        title.setObjectName("scriptingStudioIntegratedToolsHeading")
        outer.addWidget(title)
        text = QtWidgets.QLabel(
            "GhostScripter's asset library, GFF/blueprint editor, GIT placement editor, log viewer, and tutorials are preserved through GhostStudio's integrated workbenches. "
            "They open separately so the scripting window stays readable.",
            self,
        )
        text.setWordWrap(True)
        outer.addWidget(text)
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        for index, (route, label, description) in enumerate(self._ROUTES):
            group = QtWidgets.QGroupBox(label, self)
            layout = QtWidgets.QVBoxLayout(group)
            detail = QtWidgets.QLabel(description, group)
            detail.setWordWrap(True)
            button = QtWidgets.QPushButton(f"Open {label}", group)
            button.setObjectName(f"scriptingStudioRoute{route.title().replace('_', '')}")
            button.clicked.connect(lambda _checked=False, key=route: self.routeRequested.emit(key))
            layout.addWidget(detail)
            layout.addStretch(1)
            layout.addWidget(button)
            grid.addWidget(group, index // 2, index % 2)
        outer.addLayout(grid)
        outer.addStretch(1)

        automation = QtWidgets.QGroupBox("Automation compatibility", self)
        automation_layout = QtWidgets.QVBoxLayout(automation)
        automation_text = QtWidgets.QLabel(
            "GhostScripter MCP command names are mapped to GhostStudio's KotorMCP automation owner. "
            "Read operations remain safe by default; writes retain GhostStudio validation and explicit-target gates.",
            automation,
        )
        automation_text.setWordWrap(True)
        automation_layout.addWidget(automation_text)
        outer.addWidget(automation)

    def apply_ghost_theme(self, _theme: Any) -> None:
        self.setPalette(QtWidgets.QApplication.palette())
        self.update()

    def apply_ghost_layout(self, layout: Any) -> None:
        spacing_value = getattr(layout, "spacing_value", None)
        if callable(spacing_value) and self.layout() is not None:
            self.layout().setSpacing(int(spacing_value("panelSpacing", 10)))


__all__ = ["QtScriptingIntegratedToolsPage"]
