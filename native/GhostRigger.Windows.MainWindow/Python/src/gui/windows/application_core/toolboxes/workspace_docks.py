"""Workspace dock behavior for the GhostRigger main window."""

from __future__ import annotations

from typing import Optional

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.gui.qt_lib.assets.qt_theme import make_scrollable_panel
from src.gui.qt_lib.dialogs.qt_settings_dialog import save_settings
from src.gui.windows.application_core.application_core_lib.shared.dock_hosts import QtDetachableDockWidget, QtFloatingDockHost
from src.gui.windows.application_core.application_core_lib.functions.qt_helpers import _qt_object_alive


class WorkspaceDockMixin:
    """Detachable workspace panel behavior composed into ``QtGhostRiggerMainWindow``."""

    def _configure_dock_toggle_action(self, action: QtGui.QAction, key: str, show_callback) -> None:
        action.setCheckable(True)
        action.triggered.connect(lambda checked=False, k=key, callback=show_callback: self._toggle_dock_action(k, checked, callback))
        self._dock_toggle_actions[key] = action

    def _toggle_dock_action(self, key: str, checked: bool, show_callback) -> None:
        dock = getattr(self, "_detachable_panels", {}).get(key)
        if dock is None:
            self._not_migrated(key)
            self._sync_dock_toggle_action(key, False)
            return
        if checked:
            show_callback()
        else:
            host = self._host_for_dock_key(key)
            if host is not None and key in getattr(host, "dock_keys", []):
                dock.hide()
                if not any(
                    panel_key != key and getattr(self._detachable_panels.get(panel_key), "isVisible", lambda: False)()
                    for panel_key in getattr(host, "dock_keys", [])
                ):
                    host.hide()
            else:
                dock.hide()

    def _sync_dock_toggle_action(self, key: str, checked: bool) -> None:
        action = getattr(self, "_dock_toggle_actions", {}).get(key)
        if action is None:
            return
        action.setChecked(bool(checked))

    def _workspace_dock_areas(self) -> QtCore.Qt.DockWidgetArea:
        return QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea | QtCore.Qt.BottomDockWidgetArea

    def _create_detachable_panel(
        self,
        key: str,
        title: str,
        widget: QtWidgets.QWidget,
        area,
        *,
        scroll: bool = True,
    ) -> QtWidgets.QDockWidget:
        dock = QtDetachableDockWidget(key, title, self)
        dock.setObjectName(f"{key}Dock")
        if scroll:
            dock.setWidget(make_scrollable_panel(widget, f"{key}DockScroll", dock))
        else:
            dock.setWidget(widget)
        dock.setAllowedAreas(self._workspace_dock_areas())
        dock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetClosable
            | QtWidgets.QDockWidget.DockWidgetFloatable
            | QtWidgets.QDockWidget.DockWidgetMovable
        )
        self.addDockWidget(area, dock)
        dock.hide()
        dock.topLevelChanged.connect(lambda floating, k=key: self._on_detachable_panel_top_level_changed(k, floating))
        dock.dockLocationChanged.connect(lambda area, k=key, d=dock: self._on_detachable_panel_dock_location_changed(k, d, area))
        dock.visibilityChanged.connect(lambda visible, k=key, d=dock: self._on_detachable_panel_visibility(k, d, visible))
        self._detachable_panels[key] = dock
        return dock

    def _show_detachable_panel(self, key: str):
        dock = getattr(self, "_detachable_panels", {}).get(key)
        if dock is None:
            self._not_migrated(key)
            return
        if key == "resources" and getattr(self.resource_panel, "listbox", None) is not None:
            if self.resource_panel.listbox.count() == 0:
                self._populate_resource_panel()
        dock.show()
        self._sync_dock_toggle_action(key, True)
        dock.setFloating(True)
        self._persist_selected_layout_dock_state()

    def _show_workspace_dock(self, key: str) -> None:
        dock = getattr(self, "_detachable_panels", {}).get(key)
        if dock is None:
            self._not_migrated(key)
            return
        if key == "resources" and getattr(self.resource_panel, "listbox", None) is not None:
            if self.resource_panel.listbox.count() == 0:
                self._populate_resource_panel()
        host = self._host_for_dock_key(key)
        if host is not None:
            host.show()
            host.raise_()
            host.activateWindow()
            dock.show()
            dock.raise_()
            self._sync_dock_toggle_action(key, True)
            self._persist_selected_layout_dock_state()
            return
        if dock.isFloating():
            dock.setFloating(False)
        dock.show()
        self._tab_workspace_dock_with_visible_peer(key, dock)
        dock.raise_()
        self._sync_dock_toggle_action(key, True)
        self._persist_selected_layout_dock_state()

    def _tab_workspace_dock_with_visible_peer(self, key: str, dock: QtWidgets.QDockWidget) -> None:
        if key in {"content_browser", "scene"}:
            return
        if dock.isFloating():
            return
        area = self.dockWidgetArea(dock)
        if area == QtCore.Qt.NoDockWidgetArea:
            area = self._default_dock_area_for_key(key)
        for anchor_key, anchor in getattr(self, "_detachable_panels", {}).items():
            if anchor_key == key or anchor is dock or not _qt_object_alive(anchor):
                continue
            if not anchor.isVisible() or anchor.isFloating():
                continue
            if self.dockWidgetArea(anchor) != area:
                continue
            if key in {"nodes", "2das", "resources"} and anchor_key not in {"content_browser", "scene", "nodes", "2das", "resources"}:
                continue
            if key in {"properties", "lighting", "cameras", "diagnostics", "module_meshes", "mesh_tools", "adjust_pivot"} and anchor_key in {"content_browser", "scene", "nodes", "2das", "resources"}:
                continue
            try:
                self.tabifyDockWidget(anchor, dock)
                return
            except RuntimeError:
                return

    def _detachable_dock_for_key(self, key: str, dock: Optional[QtWidgets.QDockWidget] = None):
        candidate = dock if _qt_object_alive(dock) else getattr(self, "_detachable_panels", {}).get(key)
        return candidate if _qt_object_alive(candidate) else None

    def _on_detachable_panel_top_level_changed(self, key: str, floating: bool) -> None:
        dock = self._detachable_dock_for_key(key)
        if dock is None:
            return
        self._remember_detachable_panel_state(key, dock)

    def _promote_detached_panel_window(self, key: str, dock: Optional[QtWidgets.QDockWidget] = None) -> None:
        dock = self._detachable_dock_for_key(key, dock)
        if dock is None:
            return
        if not dock.isFloating():
            return
        target_host = None
        tabify = False
        previous_host = self._floating_dock_hosts.get(key)
        host = previous_host if previous_host is not None and len(getattr(previous_host, "dock_keys", [])) <= 1 else None
        area = self._default_dock_area_for_key(key)
        if host is None:
            host = QtFloatingDockHost(self, dock.windowTitle(), key)
            self._floating_dock_hosts[key] = host
        width, height = self._detachable_panel_window_size(key)
        host.add_detachable_dock(key, dock, area, tabify=tabify)
        if host is not target_host:
            host.resize(width, height)
        QtCore.QTimer.singleShot(0, host._expand_dock_layout)
        host.show()
        host.raise_()
        host.activateWindow()

    def _show_detachable_dock_context_menu(self, key: str, dock: QtWidgets.QDockWidget, global_pos: QtCore.QPoint) -> None:
        dock = self._detachable_dock_for_key(key, dock)
        if dock is None:
            return
        menu = QtWidgets.QMenu(dock)
        current_host = self._host_for_dock_key(key)

        new_window_action = menu.addAction("Dock to New Window")
        new_window_action.triggered.connect(lambda _checked=False, k=key: self._move_detachable_panel_to_new_host(k))

        window_menu = menu.addMenu("Dock to Window")
        hosts = self._available_floating_dock_hosts(exclude_key=key)
        if hosts:
            for host in hosts:
                label = self._floating_dock_host_label(host)
                host_menu = window_menu.addMenu(label)
                placements = (
                    ("As Tab", self._default_dock_area_for_key(getattr(host, "host_key", "")), True),
                    ("Left", QtCore.Qt.LeftDockWidgetArea, False),
                    ("Right", QtCore.Qt.RightDockWidgetArea, False),
                    ("Bottom", QtCore.Qt.BottomDockWidgetArea, False),
                )
                for placement_label, area, tabify in placements:
                    action = host_menu.addAction(placement_label)
                    action.triggered.connect(
                        lambda _checked=False, k=key, h=host, a=area, t=tabify: self._move_detachable_panel_to_host(
                            k,
                            h,
                            a,
                            tabify=t,
                        )
                    )
        else:
            action = window_menu.addAction("No other floating windows")
            action.setEnabled(False)

        if current_host is not None:
            menu.addSeparator()
            return_action = menu.addAction("Return to Main Window")
            return_action.triggered.connect(lambda _checked=False, k=key: self._return_detachable_panel_to_main_window(k))

        menu.exec(global_pos)

    def _available_floating_dock_hosts(self, *, exclude_key: str = "") -> list[QtFloatingDockHost]:
        hosts: list[QtFloatingDockHost] = []
        seen: set[int] = set()
        for host in list(self._floating_dock_hosts.values()):
            if not _qt_object_alive(host):
                continue
            marker = id(host)
            if marker in seen:
                continue
            seen.add(marker)
            if exclude_key and exclude_key in getattr(host, "dock_keys", []):
                continue
            if host.isVisible():
                hosts.append(host)
        return hosts

    def _floating_dock_host_label(self, host: QtFloatingDockHost) -> str:
        keys = [key for key in getattr(host, "dock_keys", []) if key in getattr(self, "_detachable_panels", {})]
        titles = []
        for key in keys:
            dock = self._detachable_dock_for_key(key)
            if dock is not None:
                titles.append(dock.windowTitle())
        if titles:
            prefix = "Workspace" if len(titles) > 1 else "Window"
            return f"{prefix}: {' / '.join(titles)}"
        try:
            return host.windowTitle()
        except RuntimeError:
            return "Floating Window"

    def _move_detachable_panel_to_new_host(self, key: str) -> None:
        dock = self._detachable_dock_for_key(key)
        if dock is None:
            return
        current_host = self._host_for_dock_key(key)
        if current_host is not None and len(getattr(current_host, "dock_keys", [])) == 1:
            current_host.show()
            current_host.raise_()
            current_host.activateWindow()
            return
        host = QtFloatingDockHost(self, dock.windowTitle(), key)
        self._floating_dock_hosts[key] = host
        host.add_detachable_dock(key, dock, self._default_dock_area_for_key(key))
        width, height = self._detachable_panel_window_size(key)
        host.resize(width, height)
        QtCore.QTimer.singleShot(0, host._expand_dock_layout)
        host.show()
        host.raise_()
        host.activateWindow()

    def _detachable_panel_window_size(self, key: str) -> tuple[int, int]:
        default_width, default_height = getattr(self, "_detachable_panel_sizes", {}).get(key, (760, 520))
        saved = self.settings_data.get("theme_layout", {}).get("panel_sizes", {}).get(key, {})
        use_saved = isinstance(saved, dict) and bool(saved.get("floating"))
        width = int(saved.get("width", default_width)) if use_saved else default_width
        height = int(saved.get("height", default_height)) if use_saved else default_height
        if key == "content_browser":
            width = max(width, default_width)
            height = max(height, default_height)
        return max(240, width), max(180, height)

    def _move_detachable_panel_to_host(
        self,
        key: str,
        host: QtFloatingDockHost,
        area,
        *,
        tabify: bool = True,
    ) -> None:
        dock = self._detachable_dock_for_key(key)
        if dock is None or not _qt_object_alive(host):
            return
        host.add_detachable_dock(key, dock, area, tabify=tabify)
        host.show()
        host.raise_()
        host.activateWindow()
        dock.raise_()

    def _return_detachable_panel_to_main_window(self, key: str) -> None:
        dock = self._detachable_dock_for_key(key)
        if dock is None:
            return
        self._remove_dock_key_from_floating_hosts(key)
        self._dock_rehosting = True
        try:
            if dock.isFloating():
                dock.setFloating(False)
            previous_parent = dock.parentWidget()
            if isinstance(previous_parent, QtWidgets.QMainWindow) and previous_parent is not self:
                try:
                    if previous_parent.centralWidget() is dock:
                        previous_parent.takeCentralWidget()
                    else:
                        previous_parent.removeDockWidget(dock)
                except Exception:
                    pass
            dock.setParent(self)
            self.addDockWidget(self._default_dock_area_for_key(key), dock)
            dock.show()
            dock.raise_()
        finally:
            self._dock_rehosting = False
        self._remember_detachable_panel_state(key, dock)

    def _floating_dock_host_at(self, global_pos: QtCore.QPoint, *, exclude_key: str = ""):
        seen: set[int] = set()
        for host in list(self._floating_dock_hosts.values()):
            try:
                marker = id(host)
                if marker in seen:
                    continue
                seen.add(marker)
                if exclude_key and exclude_key in getattr(host, "dock_keys", []):
                    continue
                if host.isVisible() and host.frameGeometry().contains(global_pos):
                    return host
            except RuntimeError:
                continue
        return None

    def _dock_area_for_host_drop(self, host: QtFloatingDockHost, global_pos: QtCore.QPoint):
        local = host.mapFromGlobal(global_pos)
        width = max(1, host.width())
        height = max(1, host.height())
        if local.y() >= int(height * 0.72):
            return QtCore.Qt.BottomDockWidgetArea, False
        if int(width * 0.35) <= local.x() <= int(width * 0.65):
            return self._default_dock_area_for_key(getattr(host, "host_key", "")), True
        if local.x() < width // 2:
            return QtCore.Qt.LeftDockWidgetArea, False
        return QtCore.Qt.RightDockWidgetArea, False

    def _default_dock_area_for_key(self, key: str):
        if key in {"content_browser", "scene", "nodes", "2das", "resources"}:
            return QtCore.Qt.LeftDockWidgetArea
        if key in {"output_log", "sequence_editor"}:
            return QtCore.Qt.BottomDockWidgetArea
        return QtCore.Qt.RightDockWidgetArea

    def _host_for_dock_key(self, key: str):
        host = self._floating_dock_hosts.get(key)
        if host is not None:
            try:
                host.objectName()
                return host
            except RuntimeError:
                self._floating_dock_hosts.pop(key, None)
        for candidate in list(self._floating_dock_hosts.values()):
            try:
                candidate.objectName()
            except RuntimeError:
                for stale_key, stale_host in list(self._floating_dock_hosts.items()):
                    if stale_host is candidate:
                        self._floating_dock_hosts.pop(stale_key, None)
                continue
            if key in getattr(candidate, "dock_keys", []):
                return candidate
        return None

    def _remove_dock_key_from_floating_hosts(self, key: str, *, keep_host=None) -> None:
        for host in list(dict.fromkeys(self._floating_dock_hosts.values())):
            try:
                dock_keys = getattr(host, "dock_keys", [])
            except RuntimeError:
                continue
            if host is keep_host:
                continue
            if key in dock_keys:
                dock_keys.remove(key)
                host._refresh_title()
            if not dock_keys:
                host.hide()
                for mapped_key, mapped_host in list(self._floating_dock_hosts.items()):
                    if mapped_host is host:
                        self._floating_dock_hosts.pop(mapped_key, None)
            else:
                host._promote_single_dock_to_central()
                QtCore.QTimer.singleShot(0, host._expand_dock_layout)
        if keep_host is None:
            self._floating_dock_hosts.pop(key, None)

    def _close_floating_dock_host(self, host: QtFloatingDockHost) -> None:
        self._dock_rehosting = True
        try:
            for key in list(host.dock_keys):
                dock = getattr(self, "_detachable_panels", {}).get(key)
                if not _qt_object_alive(dock):
                    continue
                try:
                    if host.centralWidget() is dock:
                        host.takeCentralWidget()
                    else:
                        host.removeDockWidget(dock)
                except Exception:
                    pass
                dock.setParent(self)
                self.addDockWidget(self._default_dock_area_for_key(key), dock)
                dock.hide()
                self._remember_detachable_panel_state(key, dock)
                self._floating_dock_hosts.pop(key, None)
        finally:
            self._dock_rehosting = False
        for key, candidate in list(self._floating_dock_hosts.items()):
            if candidate is host:
                self._floating_dock_hosts.pop(key, None)

    def _remember_detachable_panel_state(self, key: str, dock: QtWidgets.QDockWidget) -> None:
        dock = self._detachable_dock_for_key(key, dock)
        if dock is None:
            return
        host = self._host_for_dock_key(key)
        size_source = host if host is not None else dock
        try:
            width = size_source.width()
            height = size_source.height()
        except RuntimeError:
            width = dock.width()
            height = dock.height()
            host = None
        sizes = self.settings_data.setdefault("theme_layout", {}).setdefault("panel_sizes", {})
        sizes[key] = {
            "width": max(120, width),
            "height": max(120, height),
            "floating": bool(dock.isFloating() or host is not None),
        }
        try:
            save_settings(self.settings_path, self.settings_data)
        except Exception:
            pass
        self._persist_selected_layout_dock_state()

    def _profile_panel_id_for_dock_key(self, key: str) -> str:
        return {
            "content_browser": "contentBrowser",
            "scene": "scene",
            "properties": "properties",
            "animations": "animationLibrary",
            "nodes": "nodes",
            "lighting": "lighting",
            "cameras": "cameras",
            "module_meshes": "moduleMeshes",
            "sprite_materials": "spriteMaterials",
            "mesh_tools": "meshTools",
            "adjust_pivot": "adjustPivot",
            "2das": "2das",
            "resources": "resources",
            "diagnostics": "diagnostics",
            "sequence_editor": "sequenceEditor",
        }.get(key, key)

    def _dock_area_name(self, area) -> str:
        if area == QtCore.Qt.RightDockWidgetArea:
            return "right"
        if area == QtCore.Qt.BottomDockWidgetArea:
            return "bottom"
        if area == QtCore.Qt.TopDockWidgetArea:
            return "top"
        return "left"

    def _persist_selected_layout_dock_state(self) -> None:
        if bool(getattr(self, "_applying_ghost_layout", False)):
            return
        layout_id = str(getattr(self.layout_manager.settings, "selected_layout", "") or "default")
        docks = getattr(self, "_detachable_panels", {})
        if not isinstance(docks, dict):
            return
        panels: dict[str, dict] = {}
        for key, dock in docks.items():
            if not _qt_object_alive(dock):
                continue
            panel_id = self._profile_panel_id_for_dock_key(key)
            area_name = self._dock_area_name(self.dockWidgetArea(dock))
            min_width = 0 if key == "content_browser" else max(120, dock.minimumWidth())
            panels[panel_id] = {
                "visible": bool(dock.isVisible()),
                "region": area_name,
                "min_width": min_width,
                "preferred_width": max(120, dock.width()),
                "min_height": max(80, dock.minimumHeight()),
                "preferred_height": max(120, dock.height()),
            }

        visited: set[str] = set()
        groups: list[dict] = []
        for key, dock in docks.items():
            if key in visited or not _qt_object_alive(dock) or not dock.isVisible() or dock.isFloating():
                continue
            tabbed = [
                other_key
                for other_key, other_dock in docks.items()
                if other_key != key
                and _qt_object_alive(other_dock)
                and other_dock in self.tabifiedDockWidgets(dock)
                and other_dock.isVisible()
            ]
            group_docks = [key, *tabbed]
            visited.update(group_docks)
            groups.append(
                {
                    "id": f"user_{self._dock_area_name(self.dockWidgetArea(dock))}_{len(groups) + 1}",
                    "area": self._dock_area_name(self.dockWidgetArea(dock)),
                    "mode": "tabbed" if len(group_docks) > 1 else "tabbed",
                    "visible": True,
                    "active": key,
                    "docks": group_docks,
                }
            )

        theme_layout = self.settings_data.setdefault("theme_layout", {})
        overrides = theme_layout.setdefault("layout_overrides", {})
        overrides[layout_id] = {"panels": panels, "dock_groups": groups}
        self.layout_manager.settings.layout_overrides = dict(overrides)
        try:
            save_settings(self.settings_path, self.settings_data)
        except Exception:
            pass

    def _on_detachable_panel_visibility(self, key: str, dock: QtWidgets.QDockWidget, visible: bool) -> None:
        dock = self._detachable_dock_for_key(key, dock)
        if dock is None:
            return
        self._sync_dock_toggle_action(key, visible)
        if key == "adjust_pivot":
            self.settings_data["show_adjust_pivot_toolbox"] = bool(visible)
            try:
                save_settings(self.settings_path, self.settings_data)
            except Exception:
                pass
        if visible:
            return
        self._remember_detachable_panel_state(key, dock)
        if dock.isFloating():
            dock.setFloating(False)

    def _on_detachable_panel_dock_location_changed(self, key: str, dock: QtWidgets.QDockWidget, area) -> None:
        dock = self._detachable_dock_for_key(key, dock)
        if dock is None:
            return
        if area != QtCore.Qt.TopDockWidgetArea:
            self._remember_detachable_panel_state(key, dock)
            return
        left_keys = {"content_browser", "scene", "nodes", "2das", "resources"}
        fallback = QtCore.Qt.LeftDockWidgetArea if key in left_keys else QtCore.Qt.RightDockWidgetArea
        QtCore.QTimer.singleShot(0, lambda d=dock, a=fallback: self.addDockWidget(a, d))
