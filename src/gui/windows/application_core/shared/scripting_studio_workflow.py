"""Main-shell lifecycle for the standalone GhostStudio Scripting Suite.

The workbench stays outside Map Studio so level-authoring chrome remains
focused.  This mixin owns only window/controller composition and the typed
resource hand-off back to Map Studio.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from PySide6 import QtCore, QtWidgets


def _window_is_alive(window: object) -> bool:
    if window is None:
        return False
    try:
        import shiboken6

        return bool(shiboken6.isValid(window))
    except Exception:
        return isinstance(window, QtWidgets.QWidget)


class ScriptingStudioWorkflowMixin:
    """Compose and reuse GhostStudio's native narrative-authoring workbench."""

    def _open_scripting_dialogue_studio_window(
        self,
        context: Mapping[str, Any] | bool | None = None,
    ):
        if isinstance(context, bool):
            context = None
        window = getattr(self, "scripting_dialogue_studio_window", None)
        controller = getattr(self, "scripting_dialogue_studio_controller", None)
        if not _window_is_alive(window):
            from src.gui.controllers.scripting_suite_controller import ScriptingSuiteController
            from src.gui.qt_lib.windows.qt_scripting_dialogue_studio import (
                QtScriptingDialogueStudioWindow,
            )

            window = QtScriptingDialogueStudioWindow(self)
            resource_manager = getattr(self, "_resource_manager", None)
            if resource_manager is None:
                get_manager = getattr(self, "_get_resource_manager", None)
                if callable(get_manager):
                    try:
                        resource_manager = get_manager()
                    except Exception:
                        resource_manager = None
            saved_root = Path(getattr(self, "app_root", Path.cwd())) / "Saved" / "ScriptingStudio"
            controller = ScriptingSuiteController(
                window,
                resource_manager=resource_manager,
                output_root=(
                    saved_root / "Build"
                ),
                recent_store_path=saved_root / "recent-projects.json",
                parent=window,
            )
            controller.buildCompleted.connect(self._on_scripting_studio_build_completed)
            controller.buildInvalidated.connect(self._on_scripting_studio_build_invalidated)
            failure = getattr(controller, "operationFailed", None)
            if failure is not None:
                failure.connect(self._on_scripting_studio_operation_failed)
            external_asset = getattr(controller, "externalAssetRequested", None)
            if external_asset is not None:
                external_asset.connect(self._on_scripting_studio_external_asset_requested)
            integrated_tools = getattr(window, "integrated_tools_page", None)
            route_signal = getattr(integrated_tools, "routeRequested", None)
            if route_signal is not None:
                route_signal.connect(self._on_scripting_studio_integrated_route)
            self.scripting_dialogue_studio_window = window
            self.scripting_dialogue_studio_controller = controller
            window.destroyed.connect(self._clear_scripting_studio_references)

        game = str(
            (dict(context).get("game") if isinstance(context, Mapping) else "")
            or getattr(self, "_current_game", "")
            or "K2"
        ).upper()
        window.set_target_game(game)
        if controller is not None:
            if isinstance(context, Mapping):
                controller.open_context(self._scripting_context_with_map_participants(context))

        window.show()
        window.raise_()
        window.activateWindow()
        return window

    def _scripting_context_with_map_participants(
        self,
        context: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Attach real Map Studio creature placements to a DLG deep-link."""

        data = dict(context)
        source = str(data.get("source") or "").strip().casefold()
        kind = str(data.get("kind") or "").strip().casefold()
        restype = str(data.get("restype") or "").strip().upper()
        if source != "map_studio" or (kind != "dialogue" and restype != "DLG"):
            return data
        supplied = {
            "participants",
            "dialogue_participants",
            "placed_creatures",
            "module_creatures",
            "creatures",
        }
        if any(key in data for key in supplied):
            return data
        map_window = getattr(self, "module_editor_window", None)
        map_controller = getattr(map_window, "controller", None)
        getter = getattr(map_controller, "authored_gameplay_placements", None)
        try:
            placements = tuple(getter() or ()) if callable(getter) else ()
        except Exception:
            placements = ()
        data["placed_creatures"] = tuple(
            row
            for row in placements
            if str(
                (row.get("kind") if isinstance(row, Mapping) else getattr(row, "kind", ""))
                or ""
            ).strip().casefold() in {"creature", "npc", "utc"}
        )
        return data

    def _clear_scripting_studio_references(self, _obj: object = None) -> None:
        self.scripting_dialogue_studio_window = None
        self.scripting_dialogue_studio_controller = None

    def _on_scripting_studio_operation_failed(self, message: str) -> None:
        log = getattr(self, "_log", None)
        if callable(log):
            log(f"Scripting Suite: {message}", "error")

    def _on_scripting_studio_external_asset_requested(self, path: str, row: object) -> None:
        """Route project blueprints/GFF to the suite's loss-preserving editor."""

        controller = getattr(self, "scripting_dialogue_studio_controller", None)
        blueprint = getattr(controller, "blueprint_controller", None)
        if blueprint is not None and blueprint.open_path(path):
            window = getattr(self, "scripting_dialogue_studio_window", None)
            if window is not None:
                window.show_suite_page("blueprint")
            return
        self._on_scripting_studio_operation_failed(f"No integrated editor accepted {path}.")

    def _on_scripting_studio_integrated_route(self, route: str) -> None:
        """Open the stronger shared GhostStudio owner for adjacent workflows."""

        key = str(route or "").strip().lower()
        if key == "blueprint_page":
            window = getattr(self, "scripting_dialogue_studio_window", None)
            if window is not None:
                window.show_suite_page("blueprint")
            return
        if key == "tutorial_page":
            window = getattr(self, "scripting_dialogue_studio_window", None)
            if window is not None:
                window.show_suite_page("tutorial")
            return
        action_names = {
            "resource_browser": "resources_panel_action",
            "map_studio": "modules_action",
            "output_log": "output_log_panel_action",
            "settings": "settings_action",
            "tutorial": "getting_started_action",
        }
        action = getattr(self, action_names.get(key, ""), None)
        trigger = getattr(action, "trigger", None)
        if callable(trigger):
            trigger()
            return
        self._on_scripting_studio_operation_failed(f"Integrated tool route is unavailable: {route}")

    def _on_scripting_studio_build_completed(
        self,
        output_dir: str,
        resource_tuples: object,
    ) -> None:
        resources = tuple(resource_tuples or ())
        self._scripting_studio_runtime_resources = resources
        map_window = getattr(self, "module_editor_window", None)
        setter = getattr(map_window, "set_scripting_studio_resources", None)
        if callable(setter):
            setter(resources)
        log = getattr(self, "_log", None)
        if callable(log):
            log(
                f"Scripting build staged {len(resources)} runtime resource(s) in {output_dir}. "
                "Map Studio will include the validated NCS/DLG/JRL/2DA/LIP/SSF resources on its next export.",
                "success",
            )

    def _on_scripting_studio_build_invalidated(self) -> None:
        """Remove stale narrative bytes from Map Studio after any authoring edit."""

        self._scripting_studio_runtime_resources = ()
        map_window = getattr(self, "module_editor_window", None)
        setter = getattr(map_window, "set_scripting_studio_resources", None)
        if callable(setter):
            setter(())
        log = getattr(self, "_log", None)
        if callable(log):
            log(
                "Scripting Suite content changed. Rebuild narrative resources "
                "before the next Map Studio export.",
                "warning",
            )

    def _connect_map_studio_scripting_workflow(self, window: object) -> None:
        signal = getattr(window, "scriptingResourceEditRequested", None)
        if signal is not None and not bool(window.property("ghostScriptingStudioConnected")):
            signal.connect(self._open_scripting_dialogue_studio_window)
            window.setProperty("ghostScriptingStudioConnected", True)
        resources = tuple(getattr(self, "_scripting_studio_runtime_resources", ()) or ())
        setter = getattr(window, "set_scripting_studio_resources", None)
        if callable(setter) and resources:
            setter(resources)


__all__ = ["ScriptingStudioWorkflowMixin"]
