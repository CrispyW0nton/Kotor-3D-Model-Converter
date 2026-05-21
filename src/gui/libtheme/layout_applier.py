"""Runtime application of XML layout definitions."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from .layout_model import LayoutDefinition, ToolbarLayout


_BUTTON_STYLES = {
    "iconOnly": QtCore.Qt.ToolButtonIconOnly,
    "textOnly": QtCore.Qt.ToolButtonTextOnly,
    "iconText": QtCore.Qt.ToolButtonTextBesideIcon,
    "textBesideIcon": QtCore.Qt.ToolButtonTextBesideIcon,
    "textUnderIcon": QtCore.Qt.ToolButtonTextUnderIcon,
}


def button_mode_to_toolbutton_style(mode: str) -> QtCore.Qt.ToolButtonStyle:
    return _BUTTON_STYLES.get(mode, QtCore.Qt.ToolButtonTextBesideIcon)


class LayoutApplier(QtCore.QObject):
    layoutChanged = QtCore.Signal(object)

    def apply_layout(self, layout: LayoutDefinition, window: QtWidgets.QMainWindow) -> None:
        if not window.isMaximized():
            window.resize(layout.main_width, layout.main_height)
        if layout.maximized:
            window.showMaximized()
        self._apply_splitters(layout, window)
        self._apply_panels(layout, window)
        self._apply_toolbars(layout, window)
        self.layoutChanged.emit(layout)

    def apply_toolbar_button_mode(
        self,
        container: QtWidgets.QWidget,
        toolbar: ToolbarLayout,
        override_mode: str = "",
        override_icon_size: int = 0,
    ) -> None:
        mode = override_mode or toolbar.button_mode
        icon_size = int(override_icon_size or toolbar.icon_size)
        tool_style = button_mode_to_toolbutton_style(mode)
        buttons = [
            *container.findChildren(QtWidgets.QToolButton),
            *container.findChildren(QtWidgets.QPushButton),
        ]
        for button in buttons:
            full_text = button.property("_gr_full_text") or button.text()
            button.setToolTip(button.toolTip() or str(full_text))
            if isinstance(button, QtWidgets.QToolButton):
                button.setToolButtonStyle(tool_style)
            if mode == "iconOnly" and not button.icon().isNull():
                button.setProperty("_gr_saved_text", full_text)
                button.setText("")
                button.setMinimumWidth(max(icon_size + 14, 28))
            elif mode == "textOnly":
                button.setText(str(full_text))
                button.setIconSize(QtCore.QSize(0, 0))
            else:
                button.setText(str(full_text))
                button.setIconSize(QtCore.QSize(icon_size, icon_size))
            if toolbar.height > 0:
                button.setMinimumHeight(max(22, toolbar.height - 8))

    def _apply_toolbars(self, layout: LayoutDefinition, window: QtWidgets.QMainWindow) -> None:
        main_toolbar = layout.toolbar("main")
        command_bar = getattr(window, "command_bar", None)
        if command_bar is not None:
            command_bar.setVisible(main_toolbar.visible)
            command_bar.setMinimumHeight(main_toolbar.height)
            command_bar.setMaximumHeight(main_toolbar.height)
            self.apply_toolbar_button_mode(
                command_bar,
                main_toolbar,
                getattr(window, "_button_mode_override", ""),
                getattr(window, "_icon_size_override", 0),
            )

        viewport = getattr(window, "viewport", None)
        if viewport is not None:
            apply_layout = getattr(viewport, "apply_ghost_layout", None)
            if callable(apply_layout):
                apply_layout(layout)

    def _apply_splitters(self, layout: LayoutDefinition, window: QtWidgets.QMainWindow) -> None:
        main_splitter = getattr(window, "main_splitter", None)
        vertical_splitter = getattr(window, "vertical_splitter", None)
        if main_splitter is not None:
            left = layout.panel("library").preferred_width
            right = layout.panel("properties").preferred_width
            mesh_tools = layout.panel("meshTools")
            if mesh_tools.visible:
                right = max(right, mesh_tools.preferred_width)
            center = max(layout.viewport.preferred_width, layout.viewport.min_width)
            main_splitter.setHandleWidth(layout.spacing_value("splitterHandleWidth", 6))
            main_splitter.setSizes([left, center, right])
        if vertical_splitter is not None:
            bottom = layout.panel("outputLog")
            vertical_splitter.setHandleWidth(layout.spacing_value("splitterHandleWidth", 6))
            vertical_splitter.setSizes([max(500, layout.main_height - bottom.preferred_height), bottom.preferred_height])

    def _apply_panels(self, layout: LayoutDefinition, window: QtWidgets.QMainWindow) -> None:
        pairs = {
            "library": getattr(window, "left_tabs", None),
            "properties": getattr(window, "right_tabs", None),
            "outputLog": getattr(window, "log_panel", None),
        }
        for panel_id, widget in pairs.items():
            if widget is None:
                continue
            panel = layout.panel(panel_id)
            widget.setVisible(panel.visible)
            if panel_id != "outputLog" and panel.min_width:
                widget.setMinimumWidth(panel.min_width)
            if panel_id != "outputLog" and panel.preferred_width:
                widget.setMaximumWidth(max(panel.preferred_width + 220, panel.min_width))
            if panel.min_height:
                widget.setMinimumHeight(panel.min_height)
        viewport = getattr(window, "viewport", None)
        if viewport is not None:
            viewport.setMinimumWidth(layout.viewport.min_width)

        docks = getattr(window, "_detachable_panels", {})
        mesh_dock = docks.get("mesh_tools") if isinstance(docks, dict) else None
        mesh_panel = layout.panel("meshTools")
        if mesh_dock is not None:
            mesh_dock.setVisible(mesh_panel.visible)
            mesh_dock.resize(mesh_panel.preferred_width, max(520, mesh_panel.preferred_height))
