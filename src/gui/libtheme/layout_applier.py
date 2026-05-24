"""Runtime application of XML layout definitions."""

from __future__ import annotations

import logging
import time

from PySide6 import QtCore, QtWidgets

from .layout_model import LayoutDefinition, ToolbarLayout

log = logging.getLogger(__name__)


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
        start = time.perf_counter()
        window.setUpdatesEnabled(False)
        try:
            if not window.isMaximized():
                window.resize(layout.main_width, layout.main_height)
            if layout.maximized:
                window.showMaximized()
            self._apply_splitters(layout, window)
            self._apply_panels(layout, window)
            self._apply_density_metrics(layout, window)
            self._apply_toolbars(layout, window)
            self._notify_layout_aware_widgets(layout, window)
            sync_top_rows = getattr(window, "_sync_reserved_top_rows", None)
            if callable(sync_top_rows):
                sync_top_rows()
        finally:
            window.setUpdatesEnabled(True)
            window.update()
        self.layoutChanged.emit(layout)
        log.info("Layout apply '%s': total %.1f ms", layout.id, (time.perf_counter() - start) * 1000.0)

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
            if button.property("_gr_ignore_layout_button_mode"):
                continue
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
                button.setMinimumHeight(max(16, min(toolbar.height - 8, 24)))
                button.setMaximumHeight(max(16, min(toolbar.height - 4, 28)))
            button.setMinimumWidth(max(button.minimumWidth(), toolbar.icon_size + 14 if mode == "iconOnly" else 0))

    def _apply_toolbars(self, layout: LayoutDefinition, window: QtWidgets.QMainWindow) -> None:
        main_toolbar = layout.toolbar("main")
        command_bar = getattr(window, "command_bar", None)
        command_bar_host = getattr(window, "command_bar_host", None)
        if command_bar is not None:
            command_bar.setVisible(main_toolbar.visible)
            if command_bar_host is not None:
                command_bar_host.setVisible(main_toolbar.visible)
            command_bar.setMinimumHeight(main_toolbar.height)
            layout_obj = command_bar.layout()
            if layout_obj is not None and layout_obj.hasHeightForWidth():
                command_bar.setMaximumHeight(16777215)
            else:
                command_bar.setMaximumHeight(main_toolbar.height)
            if layout_obj is not None:
                spacing = layout.spacing_value("toolbarSpacing", layout.spacing_value("toolbar.spacing", 4))
                layout_obj.setSpacing(spacing)
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
        vertical_splitter = getattr(window, "vertical_splitter", None)
        if vertical_splitter is not None:
            bottom = layout.panel("outputLog")
            vertical_splitter.setHandleWidth(layout.spacing_value("splitterHandleWidth", layout.spacing_value("splitter.handleWidth", 6)))
            vertical_splitter.setSizes([max(500, layout.main_height - bottom.preferred_height), bottom.preferred_height])

    def _apply_panels(self, layout: LayoutDefinition, window: QtWidgets.QMainWindow) -> None:
        pairs = {
            "contentBrowser": getattr(window, "content_browser_dock", None),
            "scene": getattr(window, "scene_dock", None),
            "properties": getattr(window, "properties_dock", None),
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
            if isinstance(widget, QtWidgets.QDockWidget) and panel.preferred_width:
                widget.resize(panel.preferred_width, max(panel.preferred_height, panel.min_height))
        viewport = getattr(window, "viewport", None)
        if viewport is not None:
            viewport.setMinimumWidth(layout.viewport.min_width)

        docks = getattr(window, "_detachable_panels", {})
        if isinstance(docks, dict):
            for key, panel_id in (
                ("animations", "animationLibrary"),
                ("nodes", "nodes"),
                ("lighting", "lighting"),
                ("cameras", "cameras"),
                ("module_meshes", "moduleMeshes"),
                ("mesh_tools", "meshTools"),
                ("adjust_pivot", "adjustPivot"),
                ("2das", "2das"),
                ("resources", "resources"),
            ):
                dock = docks.get(key)
                if dock is not None:
                    panel = layout.panel(panel_id)
                    if panel_id not in layout.panels:
                        dock.setVisible(False)
                        continue
                    dock.setVisible(panel.visible)
                    dock.resize(panel.preferred_width, max(520, panel.preferred_height))
        self._apply_dock_groups(layout, window)

    def _apply_dock_groups(self, layout: LayoutDefinition, window: QtWidgets.QMainWindow) -> None:
        groups = getattr(layout, "dock_groups", [])
        docks = getattr(window, "_detachable_panels", {})
        if not groups or not isinstance(docks, dict):
            return
        area_map = {
            "left": QtCore.Qt.LeftDockWidgetArea,
            "right": QtCore.Qt.RightDockWidgetArea,
            "bottom": QtCore.Qt.BottomDockWidgetArea,
            "top": QtCore.Qt.TopDockWidgetArea,
        }
        split_map = {
            "vertical": QtCore.Qt.Vertical,
            "horizontal": QtCore.Qt.Horizontal,
        }
        for group in groups:
            dock_pairs = [(key, docks[key]) for key in group.docks if key in docks and docks.get(key) is not None]
            if not dock_pairs:
                continue
            group_docks = [dock for _key, dock in dock_pairs]
            area = area_map.get(group.area, QtCore.Qt.LeftDockWidgetArea)
            anchor = group_docks[0]
            for key, dock in dock_pairs:
                return_to_main = getattr(window, "_return_detachable_panel_to_main_window", None)
                if callable(return_to_main):
                    try:
                        host = getattr(window, "_host_for_dock_key", lambda _key: None)(key)
                        if dock.isFloating() or host is not None:
                            return_to_main(key)
                    except RuntimeError:
                        continue
                try:
                    window.addDockWidget(area, dock)
                    dock.setVisible(bool(group.visible))
                except RuntimeError:
                    continue
            if group.mode == "tabbed":
                for dock in group_docks[1:]:
                    try:
                        window.tabifyDockWidget(anchor, dock)
                    except RuntimeError:
                        continue
                active_key = group.active if group.active in group.docks else group.docks[0]
                active = docks.get(active_key)
                if active is not None:
                    active.raise_()
            elif group.mode in split_map:
                orientation = split_map[group.mode]
                previous = anchor
                for dock in group_docks[1:]:
                    try:
                        window.splitDockWidget(previous, dock, orientation)
                        previous = dock
                    except RuntimeError:
                        continue

    def _apply_density_metrics(self, layout: LayoutDefinition, window: QtWidgets.QMainWindow) -> None:
        margin = layout.spacing_value("margin", 4)
        spacing = layout.spacing_value("panelSpacing", 4)
        input_height = layout.spacing_value("inputHeight", 0)
        tab_height = layout.spacing_value("tabHeight", 0)
        tab_width = layout.spacing_value("tabWidth", 0)
        tab_padding_x = layout.spacing_value("tabPaddingX", layout.spacing_value("tabPadding", 0))
        tab_padding_y = layout.spacing_value("tabPaddingY", layout.spacing_value("tabPadding", 0))
        tab_margin_x = layout.spacing_value("tabMarginX", layout.spacing_value("tabMargin", 0))
        tab_margin_y = layout.spacing_value("tabMarginY", layout.spacing_value("tabMargin", 0))
        table_row = layout.spacing_value("tableRowHeight", 0)
        tree_row = layout.spacing_value("treeRowHeight", table_row)
        group_margin = layout.spacing_value("groupboxMargin", margin + 4)
        group_spacing = layout.spacing_value("groupboxSpacing", spacing)
        for child in window.findChildren(QtWidgets.QWidget):
            child_layout = child.layout()
            if child_layout is not None:
                child_layout.setSpacing(spacing)
                if isinstance(child_layout, (QtWidgets.QVBoxLayout, QtWidgets.QHBoxLayout, QtWidgets.QGridLayout, QtWidgets.QFormLayout)):
                    child_layout.setContentsMargins(margin, margin, margin, margin)
                if isinstance(child, QtWidgets.QGroupBox):
                    child_layout.setContentsMargins(group_margin, group_margin, group_margin, group_margin)
                    child_layout.setSpacing(group_spacing)
            if input_height and isinstance(child, (QtWidgets.QLineEdit, QtWidgets.QComboBox, QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
                child.setMinimumHeight(input_height)
                child.setMaximumHeight(max(input_height + 6, input_height))
            if isinstance(child, (QtWidgets.QTableWidget, QtWidgets.QTableView)) and table_row:
                child.verticalHeader().setDefaultSectionSize(table_row)
            if isinstance(child, (QtWidgets.QTreeWidget, QtWidgets.QTreeView)) and tree_row:
                try:
                    child.setUniformRowHeights(True)
                except Exception:
                    pass
            if isinstance(child, QtWidgets.QTabWidget) and tab_height:
                child.tabBar().setMinimumHeight(tab_height)
                tab_style_parts = [f"min-height: {tab_height}px;"]
                if tab_width:
                    tab_style_parts.append(f"min-width: {tab_width}px;")
                if tab_padding_x or tab_padding_y:
                    tab_style_parts.append(f"padding: {tab_padding_y}px {tab_padding_x}px;")
                if tab_margin_x or tab_margin_y:
                    tab_style_parts.append(f"margin: {tab_margin_y}px {tab_margin_x}px;")
                child.tabBar().setStyleSheet("QTabBar::tab {" + " ".join(tab_style_parts) + "}")

    def _notify_layout_aware_widgets(self, layout: LayoutDefinition, window: QtWidgets.QMainWindow) -> None:
        for widget in window.findChildren(QtWidgets.QWidget):
            hook = getattr(widget, "apply_ghost_layout", None)
            if callable(hook):
                hook(layout)
