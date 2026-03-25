"""GIT editor modes: geometry, instance placement, and spawn point editing."""

from __future__ import annotations

import math
import os

from abc import ABC, abstractmethod
from copy import deepcopy
from types import MappingProxyType
from typing import TYPE_CHECKING, Callable, cast

from qtpy.QtCore import Qt
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QListWidgetItem, QMenu

from loggerplus import RobustLogger  # pyright: ignore[reportMissingTypeStubs]
from pykotor.extract.installation import SearchLocation
from pykotor.resource.generics.git import (
    GITCamera,
    GITCreature,
    GITDoor,
    GITEncounter,
    GITEncounterSpawnPoint,
    GITPlaceable,
    GITSound,
    GITStore,
    GITTrigger,
    GITWaypoint,
)
from toolset.gui.dialogs.instance.camera import CameraDialog
from toolset.gui.dialogs.instance.creature import CreatureDialog
from toolset.gui.dialogs.instance.door import DoorDialog
from toolset.gui.dialogs.instance.encounter import EncounterDialog
from toolset.gui.dialogs.instance.placeable import PlaceableDialog
from toolset.gui.dialogs.instance.sound import SoundDialog
from toolset.gui.dialogs.instance.store import StoreDialog
from toolset.gui.dialogs.instance.trigger import TriggerDialog
from toolset.gui.dialogs.instance.waypoint import WaypointDialog
from toolset.gui.dialogs.load_from_location_result import FileSelectionWindow, ResourceItems
from toolset.gui.widgets.renderer.walkmesh import EncounterSpawnPoint, GeomPoint
from toolset.utils.window import add_window, open_resource_editor
from utility.common.geometry import Vector3

if TYPE_CHECKING:
    from qtpy.QtCore import QPoint
    from qtpy.QtGui import QUndoStack
    from qtpy.QtWidgets import QListWidget, QWidget

    from pykotor.extract.file import LocationResult, ResourceIdentifier
    from pykotor.resource.generics.git import (
        GIT,
        GITInstance,
        GITObject,
    )
    from toolset.data.installation import HTInstallation
    from toolset.gui.editors.git.git import GITEditor
    from toolset.gui.windows.module_designer import ModuleDesigner
    from toolset.uic.qtpy.editors.git import Ui_MainWindow as Ui_GITEditor_MainWindow
    from toolset.uic.qtpy.windows.module_designer import Ui_MainWindow as Ui_ModuleDesigner_MainWindow
    from utility.common.geometry import Vector2


def _create_instance_dialog(
    parent: QWidget,
    instance: GITObject,
    installation: HTInstallation,
) -> CameraDialog | CreatureDialog | DoorDialog | EncounterDialog | PlaceableDialog | TriggerDialog | SoundDialog | StoreDialog | WaypointDialog:
    """Create the appropriate dialog for an instance based on its type."""
    dialog_map: dict[
        type[GITObject],
        Callable[[], CameraDialog | CreatureDialog | DoorDialog | EncounterDialog | PlaceableDialog | TriggerDialog | SoundDialog | StoreDialog | WaypointDialog],
    ] = {
        GITCamera: lambda: CameraDialog(parent, cast("GITCamera", instance)),
        GITCreature: lambda: CreatureDialog(parent, cast("GITCreature", instance)),
        GITDoor: lambda: DoorDialog(parent, cast("GITDoor", instance), installation),
        GITEncounter: lambda: EncounterDialog(parent, cast("GITEncounter", instance)),
        GITPlaceable: lambda: PlaceableDialog(parent, cast("GITPlaceable", instance)),
        GITTrigger: lambda: TriggerDialog(parent, cast("GITTrigger", instance), installation),
        GITSound: lambda: SoundDialog(parent, cast("GITSound", instance)),
        GITStore: lambda: StoreDialog(parent, cast("GITStore", instance)),
        GITWaypoint: lambda: WaypointDialog(parent, cast("GITWaypoint", instance), installation),
    }

    factory = dialog_map.get(instance.__class__)
    if factory is not None:
        return factory()
    raise ValueError(f"Unknown GIT instance type: {instance.__class__}")


def open_instance_dialog(
    parent: QWidget,
    instance: GITObject,
    installation: HTInstallation,
) -> int:
    dialog: CameraDialog | CreatureDialog | DoorDialog | EncounterDialog | PlaceableDialog | TriggerDialog | SoundDialog | StoreDialog | WaypointDialog = (
        _create_instance_dialog(parent, instance, installation)
    )
    return dialog.exec()


class _Mode(ABC):
    def __init__(
        self,
        editor: GITEditor | ModuleDesigner,
        installation: HTInstallation | None,
        git: GIT,
    ):
        from toolset.gui.editors.git.git import GITEditor

        self._editor: GITEditor | ModuleDesigner = editor
        self._installation: HTInstallation | None = installation
        self._git: GIT = git
        self._is_git_editor: bool = isinstance(editor, GITEditor)

        self._ui: Ui_GITEditor_MainWindow | Ui_ModuleDesigner_MainWindow = editor.ui
        self.renderer2d = editor.ui.renderArea if self._is_git_editor else editor.ui.flatRenderer

    def list_widget(self) -> QListWidget:
        return self._ui.listWidget if self._is_git_editor else self._ui.instanceList  # pyright: ignore[reportAttributeAccessIssue]

    def move_camera(self, x: float, y: float):
        self.renderer2d.camera.nudge_position(x, y)

    def rotate_camera(self, angle: float):
        self.renderer2d.camera.nudge_rotation(angle)

    def zoom_camera(self, amount: float):
        self.renderer2d.camera.nudge_zoom(amount)

    @abstractmethod
    def on_item_selection_changed(self, item: QListWidgetItem): ...
    @abstractmethod
    def on_filter_edited(self, text: str): ...
    @abstractmethod
    def on_render_context_menu(self, world: Vector2, screen: QPoint): ...
    @abstractmethod
    def open_list_context_menu(self, item: QListWidgetItem, screen: QPoint): ...
    @abstractmethod
    def update_visibility(self): ...
    @abstractmethod
    def select_underneath(self): ...
    @abstractmethod
    def delete_selected(self, *, no_undo_stack: bool = False): ...
    @abstractmethod
    def duplicate_selected(self, position: Vector3): ...
    @abstractmethod
    def move_selected(self, x: float, y: float): ...
    @abstractmethod
    def rotate_selected(self, angle: float): ...
    @abstractmethod
    def rotate_selected_to_point(self, x: float, y: float): ...
    @abstractmethod
    def update_status_bar(self, world: Vector2): ...

    @staticmethod
    def _is_first_selected_still_under_mouse(selection: list[object], under_mouse: list[object]) -> bool:
        if not selection:
            return False
        under_mouse_ids: set[int] = {id(item) for item in under_mouse}
        return id(selection[0]) in under_mouse_ids


class _InstanceMode(_Mode):
    """Mode controller for selecting, listing, and editing instance objects."""

    _INSTANCE_LABEL_SETTING: MappingProxyType[type[GITInstance], str] = MappingProxyType(
        {
            GITCreature: "creatureLabel",
            GITPlaceable: "placeableLabel",
            GITDoor: "doorLabel",
            GITStore: "storeLabel",
            GITSound: "soundLabel",
            GITWaypoint: "waypointLabel",
            GITEncounter: "encounterLabel",
            GITTrigger: "triggerLabel",
        },
    )
    _TAG_ONLY_TYPES = (GITDoor, GITWaypoint, GITTrigger)

    def __init__(
        self,
        editor: GITEditor | ModuleDesigner,
        installation: HTInstallation | None,
        git: GIT,
    ):
        super().__init__(editor, installation, git)
        RobustLogger().debug("init InstanceMode")
        self.renderer2d.hide_geom_points = True
        self.renderer2d.geometry_selection.clear()
        self.update_visibility()

    def set_selection(self, instances: list[GITInstance]):
        # set the renderer widget selection
        """Sets the selection of instances in the renderer and list widgets.

        Args:
        ----
            instances: list[GITInstance]: List of instances to select

        Processing Logic:
        ----------------
            - Select instances in the renderer widget
            - Block list widget signals to prevent selection changed signal
            - Loop through list widget items and select matching instances
            - Unblock list widget signals.
        """
        self.renderer2d.instance_selection.select(instances)

        # set the list widget selection
        selected_ids = {id(instance) for instance in instances}
        self.list_widget().blockSignals(True)
        for i in range(self.list_widget().count()):
            item = self.list_widget().item(i)
            if item is None:
                continue
            instance = item.data(Qt.ItemDataRole.UserRole)
            if instance is not None and id(instance) in selected_ids:
                self.list_widget().setCurrentItem(item)
        self.list_widget().blockSignals(False)

    def edit_selected_instance(self):
        """Edits the selected instance.

        Args:
        ----
            self: The class instance

        Processing Logic:
        ----------------
            - Gets the selected instance from the render area
            - Checks if an instance is selected
            - Gets the last selected instance from the list
            - Opens an instance dialog to edit the selected instance properties
            - Rebuilds the instance list after editing.
        """
        selection: list[GITInstance] = self.renderer2d.instance_selection.all()
        assert self._installation is not None, "Installation is required to edit selected instance"

        if selection:
            instance: GITInstance = selection[-1]
            open_instance_dialog(self._editor, instance, self._installation)
            self.build_list()

    def edit_selected_instance_resource(self):
        selection: list[GITInstance] = self.renderer2d.instance_selection.all()

        if not selection:
            return
        instance: GITInstance = selection[-1]
        resident: ResourceIdentifier | None = instance.identifier()
        assert resident is not None, "resident cannot be None in edit_selected_instance_resource({instance!r})"
        resname, restype = resident.resname, resident.restype

        order: list[SearchLocation] = [SearchLocation.CHITIN, SearchLocation.MODULES, SearchLocation.OVERRIDE]
        assert self._installation is not None, "Installation is required to edit selected instance resource"
        search: list[LocationResult] = self._installation.location(resname, restype, order)

        if self._is_git_editor:
            assert self._editor._filepath is not None, "filepath cannot be None in edit_selected_instance_resource({instance!r})"  # noqa: SLF001
            module_root: str = self._installation.get_module_root(self._editor._filepath.name).lower()  # noqa: SLF001
            edited_file_from_dot_mod = self._editor._filepath.suffix.lower() == ".mod"  # noqa: SLF001
        else:
            assert self._editor._module is not None, "module cannot be None in edit_selected_instance_resource({instance!r})"  # noqa: SLF001
            module_root = self._editor._module.root().lower()  # noqa: SLF001
            edited_file_from_dot_mod = self._editor._module.dot_mod  # noqa: SLF001

        for i, loc in reversed(list(enumerate(search))):
            if loc.filepath.parent.name.lower() == "modules":
                assert self._installation is not None, "Installation is required to edit selected instance resource"
                loc_module_root = self._installation.get_module_root(loc.filepath.name.lower())
                loc_is_dot_mod = loc.filepath.suffix.lower() == ".mod"
                if loc_module_root != module_root:
                    RobustLogger().debug(f"Removing location '{loc.filepath}' (not in our module '{module_root}')")
                    search.pop(i)
                elif loc_is_dot_mod != edited_file_from_dot_mod:
                    RobustLogger().debug(f"Removing location '{loc.filepath}' due to rim/mod check")
                    search.pop(i)
        if len(search) > 1:
            selection_window = FileSelectionWindow(search, self._installation)
            selection_window.show()
            selection_window.activateWindow()
            add_window(selection_window)
        elif search:
            open_resource_editor(search[0].as_file_resource(), self._installation)

    def edit_selected_instance_geometry(self):
        if self.renderer2d.instance_selection.last():
            self.renderer2d.instance_selection.last()
            self._editor.enter_geometry_mode()

    def edit_selected_instance_spawns(self):
        if self.renderer2d.instance_selection.last():
            self.renderer2d.instance_selection.last()
            self._editor.enter_spawn_mode()

    def add_instance(self, instance: GITInstance):
        from toolset.gui.editors.git.undo import InsertCommand

        assert self._installation is not None, "Installation is required to add instance"

        if open_instance_dialog(self._editor, instance, self._installation):
            self._git.add(instance)
            undo_stack = self._editor._controls.undo_stack if self._is_git_editor else self._editor.undo_stack  # noqa: SLF001
            undo_stack.push(InsertCommand(self._git, instance, self._editor))
            self.build_list()

    def add_instance_actions_to_menu(self, instance: GITInstance, menu: QMenu):
        """Adds instance actions to a context menu.

        Args:
        ----
            instance: {The selected GIT instance object}
            menu: {The QMenu to add actions to}.
        """
        menu.addAction("Remove").triggered.connect(self.delete_selected)  # pyright: ignore[reportOptionalMemberAccess]

        if self._is_git_editor:
            menu.addAction("Edit Instance").triggered.connect(self.edit_selected_instance)  # pyright: ignore[reportOptionalMemberAccess]

        action_edit_resource = menu.addAction("Edit Resource")
        action_edit_resource.triggered.connect(self.edit_selected_instance_resource)  # pyright: ignore[reportOptionalMemberAccess]
        action_edit_resource.setEnabled(not isinstance(instance, GITCamera))  # pyright: ignore[reportOptionalMemberAccess]
        menu.addAction(action_edit_resource)

        if isinstance(instance, (GITEncounter, GITTrigger)):
            menu.addAction("Edit Geometry").triggered.connect(self.edit_selected_instance_geometry)  # pyright: ignore[reportOptionalMemberAccess]

        if isinstance(instance, GITEncounter):
            menu.addAction("Edit Spawn Points").triggered.connect(self.edit_selected_instance_spawns)  # pyright: ignore[reportOptionalMemberAccess]
        menu.addSeparator()
        self.add_resource_sub_menu(menu, instance)

    def add_resource_sub_menu(self, menu: QMenu, instance: GITObject) -> QMenu:
        if isinstance(instance, GITCamera):
            return menu
        locations = self._installation.location(*instance.identifier().unpack())  # pyright: ignore[reportOptionalMemberAccess]
        if not locations:
            return menu

        # Create the main context menu
        file_menu = menu.addMenu("File Actions")
        assert file_menu is not None

        if self._is_git_editor:
            valid_filepaths = [self._editor._filepath]  # noqa: SLF001
        else:
            assert self._editor._module is not None  # noqa: SLF001
            valid_filepaths = [res.filepath() for res in self._editor._module.get_capsules() if res is not None]  # noqa: SLF001

        assert self._installation is not None, "Installation is required to add resource submenu"
        override_path = self._installation.override_path()
        # Iterate over each location to create submenus
        for result in locations:
            # Create a submenu for each location
            if result.filepath not in valid_filepaths:
                continue
            if os.path.commonpath([result.filepath, override_path]) == str(override_path):
                display_path = result.filepath.relative_to(override_path.parent)
            else:
                display_path = result.filepath.joinpath(str(instance.identifier())).relative_to(self._installation.path())
            loc_menu: QMenu | None = file_menu.addMenu(str(display_path))  # pyright: ignore[reportOptionalMemberAccess]
            assert loc_menu is not None, "loc_menu cannot be None in add_resource_submenu({instance!r})"
            ResourceItems(resources=[result]).build_menu(loc_menu)

        def more_info():
            selection_window = FileSelectionWindow(locations, self._installation)
            selection_window.show()
            selection_window.activateWindow()
            add_window(selection_window)

        file_menu.addAction("Details...").triggered.connect(more_info)  # pyright: ignore[reportOptionalMemberAccess]
        return menu

    def _get_instance_label_name(self, instance: GITObject) -> str | None:
        """Get the display name for an instance based on settings."""
        if isinstance(instance, GITCamera):
            return str(instance.camera_id)

        # O(1) lookup: instance types are concrete (no subclasses in GIT list)
        settings_attr = self._INSTANCE_LABEL_SETTING.get(instance.__class__)
        if settings_attr is None:
            return None

        label_setting = getattr(self._editor.settings, settings_attr, "tag")
        if label_setting == "tag":
            if isinstance(instance, self._TAG_ONLY_TYPES):
                return instance.tag
            return self._editor.get_instance_external_tag(instance)
        if label_setting == "name":
            if isinstance(instance, GITWaypoint) and self._installation is not None:
                return self._installation.string(instance.name, "")
            return self._editor.get_instance_external_name(instance)
        return None

    def set_list_item_label(self, item: QListWidgetItem, instance: GITObject):
        assert self._installation is not None, "Installation is required to set list item label"
        item.setData(Qt.ItemDataRole.UserRole, instance)
        item.setToolTip(self.get_instance_tooltip(instance))

        assert self._is_git_editor, "InstanceMode is only available in GITEditor"

        name = self._get_instance_label_name(instance)
        if isinstance(instance, GITCamera):
            item.setText(name or "")
            return

        ident = instance.identifier()
        text: str = name or ""
        if not name:
            text = ident and ident.resname or ""
            font = item.font()
            font.setItalic(True)
            item.setFont(font)

        item.setText(text)

    def get_instance_tooltip(self, instance: GITObject) -> str:
        if isinstance(instance, GITCamera):
            return f"Struct Index: {self._struct_index(instance)}\nCamera ID: {instance.camera_id}"
        return f"Struct Index: {self._struct_index(instance)}\nResRef: {self._instance_reference_text(instance)}"

    def _instance_reference_text(self, instance: GITObject, *, camera_fallback: str = "") -> str:
        if isinstance(instance, GITCamera):
            return camera_fallback
        identifier = instance.identifier()
        return "" if identifier is None else identifier.resname

    def _build_instance_index_map(
        self,
        instances: list[GITInstance],
    ) -> dict[int, int]:
        return {id(instance): index for index, instance in enumerate(instances)}

    def _struct_index(self, instance: GITInstance, *, instances: list[GITInstance] | None = None, index_map: dict[int, int] | None = None) -> int:
        if instances is None:
            instances = self._git.instances()
        if index_map is None:
            index_map = self._build_instance_index_map(instances)
        struct_index = index_map.get(id(instance))
        if struct_index is None:
            return self._git.index(instance)
        return struct_index

    def _instance_sort_key(self, instance: GITObject) -> str:
        if isinstance(instance, GITCamera):
            return str(instance.camera_id).rjust(9, "0")
        return self._instance_reference_text(instance).rjust(9, "0")

    def _is_rotatable_instance(self, instance: GITObject) -> bool:
        return isinstance(instance, (GITCamera, GITCreature, GITDoor, GITPlaceable, GITStore, GITWaypoint))

    def _rotation_delta_to_point(self, instance: GITObject, yaw: float, current_angle: float) -> float:
        return yaw - current_angle if isinstance(instance, GITCamera) else -yaw + current_angle

    def _show_world_status(self, world: Vector2, detail: str = "") -> None:
        suffix = f" {detail}" if detail else ""
        self._editor.statusBar().showMessage(f"({world.x:.1f}, {world.y:.1f}){suffix}")  # pyright: ignore[reportOptionalMemberAccess]

    # region Interface Methods
    def on_filter_edited(self, text: str):
        self.renderer2d.instance_filter = text
        self.build_list()

    def on_item_selection_changed(self, item: QListWidgetItem):
        self.set_selection([] if item is None else [item.data(Qt.ItemDataRole.UserRole)])

    def update_status_bar(self, world: Vector2):
        under_mouse = self.renderer2d.instances_under_mouse()
        if under_mouse and under_mouse[-1] is not None:
            instance: GITInstance = under_mouse[-1]
            self._show_world_status(world, self._instance_reference_text(instance))
            return
        self._show_world_status(world)

    def open_list_context_menu(self, item: QListWidgetItem, point: QPoint):  # pyright: ignore[reportIncompatibleMethodOverride]
        if item is None:
            return

        instance = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self.list_widget())

        self.add_instance_actions_to_menu(instance, menu)

        menu.popup(point)

    def _get_render_context_menu(self, world: Vector2, menu: QMenu):
        under_mouse: list[GITInstance] = self.renderer2d.instances_under_mouse()
        git_instances: list[GITInstance] = self._editor.git().instances()
        instance_indices = self._build_instance_index_map(git_instances)
        if not self.renderer2d.instance_selection.isEmpty():
            last = self.renderer2d.instance_selection.last()
            assert last is not None, f"last cannot be None in _get_render_context_menu({world!r}, {under_mouse!r})"
            self.add_instance_actions_to_menu(last, menu)
        else:
            self.add_insert_actions_to_menu(menu, world)
        if under_mouse:
            menu.addSeparator()
            for instance in under_mouse:
                icon = QIcon(self.renderer2d.instance_pixmap(instance))
                reference = self._instance_reference_text(instance)
                index = self._struct_index(instance, instances=git_instances, index_map=instance_indices)

                instance_action = menu.addAction(icon, f"[{index}] {reference}")
                instance_action.triggered.connect(lambda _=None, inst=instance: self.set_selection([inst]))  # pyright: ignore[reportOptionalMemberAccess]
                instance_action.setEnabled(instance not in self.renderer2d.instance_selection.all())  # pyright: ignore[reportOptionalMemberAccess]
                menu.addAction(instance_action)

    def on_render_context_menu(self, world: Vector2, point: QPoint):  # pyright: ignore[reportIncompatibleMethodOverride]
        """Renders context menu on right click.

        Args:
        ----
            self: {The class instance}
            world: {The world coordinates clicked}
            point: {The screen coordinates clicked}.

        Renders context menu:
            - Adds instance creation actions if no selection
            - Adds instance actions to selected instance if single selection
            - Adds deselect action for instances under mouse
        """
        menu = QMenu(self.list_widget())
        self._get_render_context_menu(world, menu)
        menu.popup(point)

    def add_insert_actions_to_menu(self, menu: QMenu, world: Vector2):
        menu.addAction("Insert Creature").triggered.connect(lambda: self.add_instance(GITCreature(world.x, world.y)))  # pyright: ignore[reportOptionalMemberAccess]
        menu.addAction("Insert Door").triggered.connect(lambda: self.add_instance(GITDoor(world.x, world.y)))  # pyright: ignore[reportOptionalMemberAccess]
        menu.addAction("Insert Placeable").triggered.connect(lambda: self.add_instance(GITPlaceable(world.x, world.y)))  # pyright: ignore[reportOptionalMemberAccess]
        menu.addAction("Insert Store").triggered.connect(lambda: self.add_instance(GITStore(world.x, world.y)))  # pyright: ignore[reportOptionalMemberAccess]
        menu.addAction("Insert Sound").triggered.connect(lambda: self.add_instance(GITSound(world.x, world.y)))  # pyright: ignore[reportOptionalMemberAccess]
        menu.addAction("Insert Waypoint").triggered.connect(lambda: self.add_instance(GITWaypoint(world.x, world.y)))  # pyright: ignore[reportOptionalMemberAccess]
        menu.addAction("Insert Camera").triggered.connect(lambda: self.add_instance(GITCamera(world.x, world.y)))  # pyright: ignore[reportOptionalMemberAccess]
        menu.addAction("Insert Encounter").triggered.connect(lambda: self.add_instance(GITEncounter(world.x, world.y)))  # pyright: ignore[reportOptionalMemberAccess]

        simple_trigger = GITTrigger(world.x, world.y)
        simple_trigger.geometry.extend(
            [
                Vector3(0.0, 0.0, 0.0),
                Vector3(3.0, 0.0, 0.0),
                Vector3(3.0, 3.0, 0.0),
                Vector3(0.0, 3.0, 0.0),
            ],
        )
        menu.addAction("Insert Trigger").triggered.connect(lambda: self.add_instance(simple_trigger))  # pyright: ignore[reportOptionalMemberAccess]

    def build_list(self):
        self.list_widget().clear()

        instances: list[GITInstance] = sorted(self._git.instances(), key=self._instance_sort_key)
        filter_text = self._ui.filterEdit.text().lower()  # pyright: ignore[reportAttributeAccessIssue]
        for instance in instances:
            camera_fallback = str(instance.camera_id) if isinstance(instance, GITCamera) else ""
            filter_source = self._instance_reference_text(instance, camera_fallback=camera_fallback)
            is_visible: bool | None = self.renderer2d.is_instance_visible(instance)
            is_filtered: bool = filter_text in filter_source.lower()

            if is_visible and is_filtered:
                icon = QIcon(self.renderer2d.instance_pixmap(instance))
                item = QListWidgetItem(icon, "")
                self.set_list_item_label(item, instance)
                self.list_widget().addItem(item)

    def update_visibility(self):
        self.renderer2d.hide_creatures = not self._ui.viewCreatureCheck.isChecked()
        self.renderer2d.hide_placeables = not self._ui.viewPlaceableCheck.isChecked()
        self.renderer2d.hide_doors = not self._ui.viewDoorCheck.isChecked()
        self.renderer2d.hide_triggers = not self._ui.viewTriggerCheck.isChecked()
        self.renderer2d.hide_encounters = not self._ui.viewEncounterCheck.isChecked()
        self.renderer2d.hide_waypoints = not self._ui.viewWaypointCheck.isChecked()
        self.renderer2d.hide_sounds = not self._ui.viewSoundCheck.isChecked()
        self.renderer2d.hide_stores = not self._ui.viewStoreCheck.isChecked()
        self.renderer2d.hide_cameras = not self._ui.viewCameraCheck.isChecked()
        self.build_list()

    def select_underneath(self):
        under_mouse: list[GITInstance] = self.renderer2d.instances_under_mouse()
        selection: list[GITInstance] = self.renderer2d.instance_selection.all()

        # Do not change the selection if the selected instance if its still underneath the mouse
        if self._is_first_selected_still_under_mouse(selection, under_mouse):
            RobustLogger().info(f"Not changing selection: selected instance '{selection[0].classification()}' is still underneath the mouse.")
            return

        if under_mouse:
            self.set_selection([under_mouse[-1]])
        else:
            self.set_selection([])

    def _get_undo_stack(self) -> QUndoStack:
        from toolset.gui.editors.git.git import GITEditor

        undo_stack = (
            self._editor._controls.undo_stack  # noqa: SLF001
            if isinstance(self._editor, GITEditor)  # noqa: SLF001
            else self._editor.undo_stack  # noqa: SLF01
        )
        return undo_stack

    def delete_selected(
        self,
        *,
        no_undo_stack: bool = False,
    ):
        from toolset.gui.editors.git.undo import DeleteCommand

        selection = self.renderer2d.instance_selection.all()
        if no_undo_stack:
            RobustLogger().info(f"Deleting selected instances without undo stack: {selection!r}")
            for instance in selection:
                self._git.remove(instance)
                self.renderer2d.instance_selection.remove(instance)
        else:
            undo_stack = self._get_undo_stack()
            RobustLogger().info(f"Pushing delete command to undo stack: {selection!r}")
            undo_stack.push(DeleteCommand(self._git, selection.copy(), self._editor))  # noqa: SLF001
        self.build_list()

    def duplicate_selected(
        self,
        position: Vector3,
        *,
        no_undo_stack: bool = False,
    ):
        from toolset.gui.editors.git.undo import DuplicateCommand

        selection = self.renderer2d.instance_selection.all()
        if selection:
            instance: GITInstance = deepcopy(selection[-1])
            if isinstance(instance, GITCamera):
                instance.camera_id = self._editor.git().next_camera_id()
            instance.position = position
            if no_undo_stack:
                RobustLogger().info(f"Adding instance to git without undo stack: {instance!r}")
                self._git.add(instance)
                self.build_list()
                self.set_selection([instance])
            else:
                undo_stack = self._get_undo_stack()
                RobustLogger().info(f"Pushing duplicate command to undo stack: {instance!r}")
                undo_stack.push(DuplicateCommand(self._git, [instance], self._editor))

    def move_selected(
        self,
        x: float,
        y: float,
        *,
        no_undo_stack: bool = False,
    ):
        RobustLogger().info(f"Moving selected instances by ({x}, {y})")
        if self._ui.lockInstancesCheck.isChecked():
            RobustLogger().info("Ignoring move_selected for instancemode, lockInstancesCheck is checked.")
            return

        for instance in self.renderer2d.instance_selection.all():
            instance.move(x, y, 0)

    def rotate_selected(self, angle: float):
        RobustLogger().info(f"Rotating selected instances by {angle} degrees")
        for instance in self.renderer2d.instance_selection.all():
            if self._is_rotatable_instance(instance):
                instance.rotate(angle, 0, 0)

    def rotate_selected_to_point(self, x: float, y: float):
        RobustLogger().info(f"Rotating selected instances to point ({x}, {y})")
        rotation_threshold = 0.05  # Threshold for rotation changes, adjust as needed
        for instance in self.renderer2d.instance_selection.all():
            if not self._is_rotatable_instance(instance):
                continue
            current_angle = -math.atan2(x - instance.position.x, y - instance.position.y)
            current_angle = (current_angle + math.pi) % (2 * math.pi) - math.pi  # Normalize to -π to π
            yaw = ((instance.yaw() or 0.01) + math.pi) % (2 * math.pi) - math.pi  # Normalize to -π to π
            rotation_difference = ((yaw - current_angle) + math.pi) % (2 * math.pi) - math.pi
            if abs(rotation_difference) < rotation_threshold:
                continue
            instance.rotate(self._rotation_delta_to_point(instance, yaw, current_angle), 0, 0)

    # endregion


class _GeometryMode(_Mode):
    def __init__(
        self,
        editor: GITEditor | ModuleDesigner,
        installation: HTInstallation | None,
        git: GIT,
        *,
        hide_others: bool = True,
    ):
        super().__init__(editor, installation, git)

        if hide_others:
            self.renderer2d.hide_creatures = True
            self.renderer2d.hide_doors = True
            self.renderer2d.hide_placeables = True
            self.renderer2d.hide_sounds = True
            self.renderer2d.hide_stores = True
            self.renderer2d.hide_cameras = True
            self.renderer2d.hide_triggers = True
            self.renderer2d.hide_encounters = True
            self.renderer2d.hide_waypoints = True
        else:
            self.renderer2d.hide_encounters = False
            self.renderer2d.hide_triggers = False
        self.renderer2d.hide_geom_points = False

    def insert_point_at_mouse(self):
        screen: QPoint = self.renderer2d.mapFromGlobal(self._editor.cursor().pos())
        world: Vector3 = self.renderer2d.to_world_coords(screen.x(), screen.y())

        instance: GITInstance = self.renderer2d.instance_selection.get(0)
        assert isinstance(instance, (GITEncounter, GITTrigger))
        point: Vector3 = world - instance.position
        new_geom_point = GeomPoint(instance, point)
        instance.geometry.append(point)
        self.renderer2d.geom_points_under_mouse().append(new_geom_point)
        self.renderer2d.geometry_selection._selection.append(new_geom_point)  # noqa: SLF001
        RobustLogger().debug(f"Inserting new geompoint, instance {instance.identifier()}. Total points: {len(list(instance.geometry))}")

    # region Interface Methods
    def on_item_selection_changed(self, item: QListWidgetItem): ...

    def on_filter_edited(self, text: str): ...

    def update_status_bar(self, world: Vector2):
        instance: GITInstance | None = self.renderer2d.instance_selection.last()
        if instance:
            self._show_world_status(world, f"Editing Geometry of {instance.identifier().resname}")  # pyright: ignore[reportOptionalMemberAccess]

    def on_render_context_menu(self, world: Vector2, screen: QPoint):
        menu = QMenu(self._editor)
        self._get_render_context_menu(world, menu)
        menu.popup(screen)

    def _get_render_context_menu(
        self,
        world: Vector2,
        menu: QMenu,
    ):
        if not self.renderer2d.geometry_selection.isEmpty():
            menu.addAction("Remove").triggered.connect(self.delete_selected)  # pyright: ignore[reportOptionalMemberAccess]

        if self.renderer2d.geometry_selection.count() == 0:
            menu.addAction("Insert").triggered.connect(self.insert_point_at_mouse)  # pyright: ignore[reportOptionalMemberAccess]

        menu.addSeparator()
        menu.addAction("Finish Editing").triggered.connect(self._editor.enter_instance_mode)  # pyright: ignore[reportOptionalMemberAccess]

    def open_list_context_menu(self, item: QListWidgetItem, screen: QPoint): ...

    def update_visibility(self): ...

    def select_underneath(self):
        under_mouse: list[GeomPoint] = self.renderer2d.geom_points_under_mouse()
        selection: list[GeomPoint] = self.renderer2d.geometry_selection.all()

        # Do not change the selection if the selected instance if its still underneath the mouse
        if self._is_first_selected_still_under_mouse(selection, under_mouse):
            RobustLogger().info(f"Not changing selection: selected instance '{selection[0].instance.classification()}' is still underneath the mouse.")
            return
        self.renderer2d.geometry_selection.select(under_mouse or [])

    def delete_selected(self, *, no_undo_stack: bool = False):
        vertex: GeomPoint | None = self.renderer2d.geometry_selection.last()
        if vertex is None:
            RobustLogger().error("Could not delete last GeomPoint, there's none selected.")
            return
        instance: GITInstance = vertex.instance
        RobustLogger().debug(f"Removing last geometry point for instance {instance.identifier()}")
        self.renderer2d.geometry_selection.remove(GeomPoint(instance, vertex.point))

    def duplicate_selected(self, position: Vector3): ...

    def move_selected(self, x: float, y: float):
        for vertex in self.renderer2d.geometry_selection.all():
            vertex.point.x += x
            vertex.point.y += y

    def rotate_selected(self, angle: float): ...

    def rotate_selected_to_point(self, x: float, y: float): ...

    # endregion


class _SpawnMode(_Mode):
    def __init__(
        self,
        editor: GITEditor | ModuleDesigner,
        installation: HTInstallation | None,
        git: GIT,
        *,
        hide_others: bool = True,
    ):
        super().__init__(editor, installation, git)

        if hide_others:
            self.renderer2d.hide_creatures = True
            self.renderer2d.hide_doors = True
            self.renderer2d.hide_placeables = True
            self.renderer2d.hide_sounds = True
            self.renderer2d.hide_stores = True
            self.renderer2d.hide_cameras = True
            self.renderer2d.hide_triggers = True
            self.renderer2d.hide_waypoints = True
            self.renderer2d.hide_encounters = False
        else:
            self.renderer2d.hide_encounters = False

        self.renderer2d.hide_geom_points = True
        self.renderer2d.hide_spawn_points = False

        self.renderer2d.geometry_selection.clear()
        self.renderer2d.spawn_selection.clear()

        # Ensure an encounter is selected; spawn points belong to an encounter instance.
        last = self.renderer2d.instance_selection.last()
        if last is not None and not isinstance(last, GITEncounter):
            self.renderer2d.instance_selection.clear()
        if self.renderer2d.instance_selection.isEmpty() and self._git.encounters:
            self.renderer2d.instance_selection.select([self._git.encounters[0]])

    def _selected_encounter(self) -> GITEncounter | None:
        inst = self.renderer2d.instance_selection.last()
        return inst if isinstance(inst, GITEncounter) else None

    def _undo_stack(self):
        # GITEditor uses the controls' undo stack; ModuleDesigner uses its own undo_stack.
        return self._editor._controls.undo_stack if self._is_git_editor else self._editor.undo_stack  # noqa: SLF001

    def _refresh(self):
        self.renderer2d.update()

    def insert_spawn_point_at_mouse(self):
        from toolset.gui.editors.git.undo import SpawnPointInsertCommand

        encounter = self._selected_encounter()
        if encounter is None:
            return
        screen: QPoint = self.renderer2d.mapFromGlobal(self._editor.cursor().pos())
        world: Vector3 = self.renderer2d.to_world_coords(screen.x(), screen.y())

        spawn = GITEncounterSpawnPoint(world.x, world.y, world.z)
        self._undo_stack().push(SpawnPointInsertCommand(encounter, spawn, self._editor))
        self.renderer2d.spawn_selection.select([EncounterSpawnPoint(encounter, spawn)])
        self._refresh()

    def _spawn_id_set(self, encounter: GITEncounter) -> set[int]:
        """Build a set of spawn point identities for O(1) membership checks."""
        return {id(spawn) for spawn in encounter.spawn_points}

    def _spawn_ref_is_current(self, sp_ref: EncounterSpawnPoint) -> bool:
        """Return whether the selected spawn reference is still present in its encounter list."""
        return id(sp_ref.spawn) in self._spawn_id_set(sp_ref.encounter)

    def _spawn_id_map_for_selection(self, selection: list[EncounterSpawnPoint]) -> dict[int, set[int]]:
        """Build encounter-id -> spawn-id-set map for selected spawn points."""
        encounters = {sp_ref.encounter for sp_ref in selection}
        return {id(encounter): self._spawn_id_set(encounter) for encounter in encounters}

    # region Interface Methods
    def on_item_selection_changed(self, item: QListWidgetItem):
        # Spawn mode does not use the instance list for selection changes.
        return

    def on_filter_edited(self, text: str):
        return

    def update_status_bar(self, world: Vector2):
        encounter = self._selected_encounter()
        msg = "Editing Spawn Points"
        if encounter is not None:
            msg = f"Editing Spawn Points of {encounter.identifier().resname}"
        if hasattr(self._editor, "statusBar"):
            self._show_world_status(world, msg)

    def on_render_context_menu(self, world: Vector2, screen: QPoint):
        menu = QMenu(self._editor)
        self._get_render_context_menu(world, menu)
        menu.popup(screen)

    def _get_render_context_menu(
        self,
        world: Vector2,
        menu: QMenu,
    ):
        if not self.renderer2d.spawn_selection.isEmpty():
            menu.addAction("Remove Spawn Point").triggered.connect(self.delete_selected)  # pyright: ignore[reportOptionalMemberAccess]
            menu.addAction("Duplicate Spawn Point Here").triggered.connect(  # pyright: ignore[reportOptionalMemberAccess]
                lambda: self.duplicate_selected(Vector3(world.x, world.y, self.renderer2d.get_z_coord(world.x, world.y)))
            )
        else:
            menu.addAction("Insert Spawn Point").triggered.connect(self.insert_spawn_point_at_mouse)  # pyright: ignore[reportOptionalMemberAccess]

        menu.addSeparator()
        menu.addAction("Finish Editing").triggered.connect(self._editor.enter_instance_mode)  # pyright: ignore[reportOptionalMemberAccess]

    def open_list_context_menu(self, item: QListWidgetItem, screen: QPoint):
        return

    def update_visibility(self):
        return

    def select_underneath(self):
        under_mouse = self.renderer2d.spawn_points_under_mouse()
        selection = self.renderer2d.spawn_selection.all()
        if self._is_first_selected_still_under_mouse(selection, under_mouse):
            return
        if under_mouse:
            self.renderer2d.spawn_selection.select([under_mouse[-1]])
        else:
            self.renderer2d.spawn_selection.select([])

    def delete_selected(self, *, no_undo_stack: bool = False):
        from toolset.gui.editors.git.undo import SpawnPointDeleteCommand

        sp_ref = self.renderer2d.spawn_selection.last()
        if sp_ref is None:
            return
        encounter = sp_ref.encounter
        spawn = sp_ref.spawn
        if not self._spawn_ref_is_current(sp_ref):
            self.renderer2d.spawn_selection.clear()
            return

        if no_undo_stack:
            encounter.spawn_points.remove(spawn)
        else:
            self._undo_stack().push(SpawnPointDeleteCommand(encounter, spawn, self._editor))
        self.renderer2d.spawn_selection.clear()
        self._refresh()

    def duplicate_selected(self, position: Vector3):
        from toolset.gui.editors.git.undo import SpawnPointInsertCommand

        sp_ref = self.renderer2d.spawn_selection.last()
        if sp_ref is None:
            return
        encounter = sp_ref.encounter
        source = sp_ref.spawn
        if not self._spawn_ref_is_current(sp_ref):
            return

        spawn = GITEncounterSpawnPoint(position.x, position.y, position.z)
        spawn.orientation = source.orientation
        self._undo_stack().push(SpawnPointInsertCommand(encounter, spawn, self._editor))
        self.renderer2d.spawn_selection.select([EncounterSpawnPoint(encounter, spawn)])
        self._refresh()

    def move_selected(self, x: float, y: float):
        active_selection = self.renderer2d.spawn_selection.all()
        encounter_spawn_ids = self._spawn_id_map_for_selection(active_selection)
        for sp_ref in active_selection:
            if id(sp_ref.spawn) not in encounter_spawn_ids[id(sp_ref.encounter)]:
                continue
            sp_ref.spawn.x += x
            sp_ref.spawn.y += y
            sp_ref.spawn.z = self.renderer2d.get_z_coord(sp_ref.spawn.x, sp_ref.spawn.y)
        self._refresh()

    def rotate_selected(self, angle: float):
        active_selection = self.renderer2d.spawn_selection.all()
        encounter_spawn_ids = self._spawn_id_map_for_selection(active_selection)
        for sp_ref in active_selection:
            if id(sp_ref.spawn) not in encounter_spawn_ids[id(sp_ref.encounter)]:
                continue
            sp_ref.spawn.orientation += angle
        self._refresh()

    def rotate_selected_to_point(self, x: float, y: float):
        active_selection = self.renderer2d.spawn_selection.all()
        encounter_spawn_ids = self._spawn_id_map_for_selection(active_selection)
        for sp_ref in active_selection:
            if id(sp_ref.spawn) not in encounter_spawn_ids[id(sp_ref.encounter)]:
                continue
            dx = x - sp_ref.spawn.x
            dy = y - sp_ref.spawn.y
            if abs(dx) < 1e-6 and abs(dy) < 1e-6:
                continue
            sp_ref.spawn.orientation = math.atan2(-dx, dy)
        self._refresh()

    # endregion
