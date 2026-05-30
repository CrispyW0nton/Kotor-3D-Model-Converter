"""Detachable dock host widgets for the GhostRigger main window."""

from __future__ import annotations

try:
    from PySide6 import QtCore, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.gui.windows.application_core.shared.qt_helpers import _qt_object_alive

class QtFloatingDockHost(QtWidgets.QMainWindow):
    """Real top-level window that can host one or more detachable dock panels."""

    def __init__(self, owner, title: str, host_key: str):
        super().__init__(None)
        self.owner = owner
        self.host_key = host_key
        self.dock_keys: list[str] = []
        self.setObjectName(f"{host_key}FloatingDockHost")
        self.setWindowTitle(title)
        try:
            self.setWindowIcon(owner.windowIcon())
        except Exception:
            pass
        self.setDockNestingEnabled(True)
        self._dock_fill_placeholder = QtWidgets.QWidget(self)
        self._dock_fill_placeholder.setObjectName(f"{host_key}DockFillPlaceholder")
        self._dock_fill_placeholder.setFixedSize(0, 0)
        self.setCentralWidget(self._dock_fill_placeholder)
        self.setDockOptions(
            QtWidgets.QMainWindow.AnimatedDocks
            | QtWidgets.QMainWindow.AllowNestedDocks
            | QtWidgets.QMainWindow.AllowTabbedDocks
            | QtWidgets.QMainWindow.GroupedDragging
        )
        all_dock_areas = (
            QtCore.Qt.LeftDockWidgetArea
            | QtCore.Qt.RightDockWidgetArea
            | QtCore.Qt.TopDockWidgetArea
            | QtCore.Qt.BottomDockWidgetArea
        )
        self.setTabPosition(all_dock_areas, QtWidgets.QTabWidget.North)
        self.setWindowFlags(
            QtCore.Qt.Window
            | QtCore.Qt.WindowMinMaxButtonsHint
            | QtCore.Qt.WindowCloseButtonHint
        )

    def add_detachable_dock(self, key: str, dock: QtWidgets.QDockWidget, area, *, tabify: bool = False) -> None:
        if not _qt_object_alive(dock):
            return
        owner = self.owner
        owner._dock_rehosting = True
        try:
            if hasattr(owner, "_remove_dock_key_from_floating_hosts"):
                owner._remove_dock_key_from_floating_hosts(key, keep_host=self)
            if not _qt_object_alive(dock):
                return
            self._relax_dock_size_limits(dock)
            if dock.isFloating():
                dock.setFloating(False)
            if not _qt_object_alive(dock):
                return
            self._relax_dock_size_limits(dock)
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
            existing_docks = [
                existing
                for existing in self.findChildren(QtWidgets.QDockWidget)
                if existing is not dock and _qt_object_alive(existing)
            ]
            self.addDockWidget(area, dock)
            self._relax_dock_size_limits(dock)
            if tabify and existing_docks:
                self.tabifyDockWidget(existing_docks[-1], dock)
            dock.show()
            if key not in self.dock_keys:
                self.dock_keys.append(key)
            owner._floating_dock_hosts[key] = self
            self._refresh_title()
            QtCore.QTimer.singleShot(0, self._expand_dock_layout)
        finally:
            owner._dock_rehosting = False

    def _refresh_title(self) -> None:
        if len(self.dock_keys) == 1:
            dock = self.owner._detachable_panels.get(self.dock_keys[0])
            self.setWindowTitle(dock.windowTitle() if _qt_object_alive(dock) else "GhostRigger Workspace")
        else:
            label = self.owner._floating_dock_host_label(self) if hasattr(self.owner, "_floating_dock_host_label") else ""
            self.setWindowTitle(label or "GhostRigger Workspace")

    def _relax_dock_size_limits(self, dock: QtWidgets.QDockWidget) -> None:
        max_size = 16777215
        dock.setMaximumSize(max_size, max_size)
        dock.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        widget = dock.widget()
        if widget is not None:
            widget.setMaximumSize(max_size, max_size)
            if widget.sizePolicy().horizontalPolicy() != QtWidgets.QSizePolicy.Expanding:
                widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, widget.sizePolicy().verticalPolicy())

    def _key_for_dock(self, dock: QtWidgets.QDockWidget) -> str:
        for key, candidate in getattr(self.owner, "_detachable_panels", {}).items():
            if candidate is dock:
                return key
        return getattr(dock, "detachable_key", "")

    def _default_area_for_key(self, key: str):
        if hasattr(self.owner, "_default_dock_area_for_key"):
            return self.owner._default_dock_area_for_key(key)
        return QtCore.Qt.LeftDockWidgetArea

    def _dock_widgets(self) -> list[QtWidgets.QDockWidget]:
        return [
            dock
            for dock in self.findChildren(QtWidgets.QDockWidget)
            if _qt_object_alive(dock) and dock.isVisible()
        ]

    def _expand_dock_layout(self) -> None:
        docks = self._dock_widgets()
        if not docks:
            return
        primary = docks[0]
        is_tab_stack = len(self.tabifiedDockWidgets(primary)) >= len(docks) - 1
        if len(docks) != 1 and not is_tab_stack:
            return
        try:
            self.resizeDocks([primary], [max(420, self.width())], QtCore.Qt.Horizontal)
            self.resizeDocks([primary], [max(320, self.height())], QtCore.Qt.Vertical)
        except Exception:
            pass

    def _promote_single_dock_to_central(self) -> None:
        self._expand_dock_layout()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        QtCore.QTimer.singleShot(0, self._expand_dock_layout)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.owner._close_floating_dock_host(self)
        event.accept()

class QtDetachableDockWidget(QtWidgets.QDockWidget):
    """Dock widget with a small workspace-routing context menu."""

    def __init__(self, key: str, title: str, owner):
        super().__init__(title, owner)
        self.detachable_key = key
        self.owner_window = owner

    def contextMenuEvent(self, event) -> None:  # noqa: N802 - Qt API
        owner = getattr(self, "owner_window", None)
        if owner is not None and hasattr(owner, "_show_detachable_dock_context_menu"):
            owner._show_detachable_dock_context_menu(self.detachable_key, self, event.globalPos())
            event.accept()
            return
        super().contextMenuEvent(event)
