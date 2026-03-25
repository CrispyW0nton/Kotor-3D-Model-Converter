"""GIT (game instance) editor: placeables, creatures, doors, and module designer integration."""

from __future__ import annotations

import sys

from pathlib import Path
from typing import TYPE_CHECKING

import qtpy

from qtpy.QtCore import (
    Signal,  # pyright: ignore[reportPrivateImportUsage]
)
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import (
    QMessageBox,  # pyright: ignore[reportPrivateImportUsage]
)

from pykotor.extract.installation import SearchLocation
from pykotor.resource.formats.bwm import read_bwm
from pykotor.resource.formats.lyt import read_lyt
from pykotor.resource.generics.git import GIT, bytes_git, read_git
from pykotor.resource.type import ResourceType
from pykotor.tools.template import extract_name, extract_tag_from_gff
from toolset.blender import BlenderEditorMode
from toolset.blender.integration import BlenderEditorMixin
from toolset.gui.common.editor_pipelines import set_exclusive_checkbox_selection
from toolset.gui.common.walkmesh_materials import get_walkmesh_material_colors
from toolset.gui.editor import Editor
from toolset.gui.editors.git.controls import GITControlScheme
from toolset.gui.editors.git.mode import _GeometryMode, _InstanceMode, _SpawnMode
from toolset.gui.widgets.installation_toolbar import FolderPathSpec
from toolset.gui.widgets.settings.editor_settings.git import GITSettings
from utility.common.geometry import Vector2

if TYPE_CHECKING:
    import os

    from qtpy.QtCore import (
        QPoint,
        Qt,  # pyright: ignore[reportPrivateImportUsage]
    )
    from qtpy.QtGui import QCloseEvent, QColor, QKeyEvent
    from qtpy.QtWidgets import (
        QCheckBox,
        QListWidgetItem,  # pyright: ignore[reportPrivateImportUsage]
        QWidget,
    )

    from pykotor.extract.file import ResourceIdentifier, ResourceResult
    from pykotor.resource.formats.bwm import BWM
    from pykotor.resource.formats.lyt import LYT
    from pykotor.resource.generics.git import GITInstance
    from toolset.data.installation import HTInstallation
    from toolset.gui.editors.git.mode import _Mode
    from utility.common.geometry import SurfaceMaterial, Vector3

if qtpy.QT5:
    pass
elif qtpy.QT6:
    pass


class GITEditor(Editor, BlenderEditorMixin):
    STANDALONE_FOLDER_PATHS = [
        FolderPathSpec("modules_folder", "Modules Folder", "Folder containing extracted module resources."),
        FolderPathSpec("override_folder", "Override Folder", "Folder containing override resources."),
    ]

    sig_settings_updated = Signal(object)  # pyright: ignore[reportPrivateImportUsage]

    def __init__(
        self,
        parent: QWidget | None,
        installation: HTInstallation | None = None,
        use_blender: bool = False,
    ):
        """Initializes the GIT editor.

        Args:
        ----
            parent: QWidget | None: The parent widget
            installation: HTInstallation | None: The installation
            use_blender: bool: Whether to use Blender for editing

        Initializes the editor UI and connects signals. Loads default settings. Initializes rendering area and mode. Clears any existing geometry.
        """
        supported = [ResourceType.GIT]
        super().__init__(parent, "GIT Editor", "git", supported, supported, installation)

        # Initialize Blender integration
        self._init_blender_integration(BlenderEditorMode.GIT_EDITOR)
        self._use_blender_mode: bool = use_blender

        from toolset.uic.qtpy.editors.git import Ui_MainWindow

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self._setup_menus()
        self._add_help_action()
        self._setup_signals()
        self._setup_hotkeys()

        self._git: GIT = GIT()
        self._layout: LYT | None = None  # Store the LYT layout for room boundary rendering
        self._mode: _Mode = _InstanceMode(self, installation, self._git)
        self._controls: GITControlScheme = GITControlScheme(self)
        self._geom_instance: GITInstance | None = None  # Used to track which trigger/encounter you are editing

        self.settings = GITSettings()

        self.material_colors: dict[SurfaceMaterial, QColor] = get_walkmesh_material_colors()

        self.name_buffer: dict[ResourceIdentifier, str] = {}
        self.tag_buffer: dict[ResourceIdentifier, str] = {}

        self.ui.renderArea.material_colors = self.material_colors
        self.ui.renderArea.hide_walkmesh_edges = True
        self.ui.renderArea.highlight_boundaries = False
        self.ui.renderArea.show_room_boundaries = True
        self.ui.renderArea.show_grid = False

        self.new()

    def _resolve_path_resource(self, resref: str, suffix: str, keys: tuple[str, ...]) -> bytes | None:
        for key in keys:
            folder = getattr(self, "_standalone_folder_paths", {}).get(key)
            if folder is None:
                continue
            path = folder / f"{resref}.{suffix}"
            if path.is_file():
                return path.read_bytes()
        return None

    def _on_installation_changed(self, installation: HTInstallation | None) -> None:
        self._installation = installation
        self._mode = _InstanceMode(self, self._installation, self._git)
        self.update_visibility()

    def _on_folder_paths_changed(self, paths: dict[str, Path | None]) -> None:
        self._standalone_folder_paths = paths

    def _setup_hotkeys(self):  # TODO: use GlobalSettings() defined hotkeys
        self.ui.actionDeleteSelected.setShortcut(QKeySequence("Del"))  # type: ignore[arg-type]
        # Use "=" (base key) for zoom in instead of "+" (which requires Shift).
        self.ui.actionZoomIn.setShortcut(QKeySequence("="))  # type: ignore[arg-type]
        self.ui.actionZoomOut.setShortcut(QKeySequence("-"))  # type: ignore[arg-type]
        self.ui.actionUndo.setShortcut(QKeySequence("Ctrl+Z"))  # type: ignore[arg-type]
        self.ui.actionRedo.setShortcut(QKeySequence("Ctrl+Shift+Z"))  # type: ignore[arg-type]

    def _setup_signals(self):
        self.ui.renderArea.sig_mouse_pressed.connect(self.on_mouse_pressed)
        self.ui.renderArea.sig_mouse_moved.connect(self.on_mouse_moved)
        self.ui.renderArea.sig_mouse_scrolled.connect(self.on_mouse_scrolled)
        self.ui.renderArea.sig_mouse_released.connect(self.on_mouse_released)
        self.ui.renderArea.sig_marquee_select.connect(self.on_marquee_select)
        self.ui.renderArea.sig_key_pressed.connect(self.on_key_pressed)
        self.ui.renderArea.customContextMenuRequested.connect(self.on_context_menu)

        self.ui.filterEdit.textEdited.connect(self.on_filter_edited)
        self.ui.listWidget.doubleClicked.connect(self.move_camera_to_selection)
        self.ui.listWidget.itemSelectionChanged.connect(self.on_item_selection_changed)
        self.ui.listWidget.customContextMenuRequested.connect(self.on_item_context_menu)

        self.ui.viewCreatureCheck.toggled.connect(self.update_visibility)
        self.ui.viewPlaceableCheck.toggled.connect(self.update_visibility)
        self.ui.viewDoorCheck.toggled.connect(self.update_visibility)
        self.ui.viewSoundCheck.toggled.connect(self.update_visibility)
        self.ui.viewTriggerCheck.toggled.connect(self.update_visibility)
        self.ui.viewEncounterCheck.toggled.connect(self.update_visibility)
        self.ui.viewWaypointCheck.toggled.connect(self.update_visibility)
        self.ui.viewCameraCheck.toggled.connect(self.update_visibility)
        self.ui.viewStoreCheck.toggled.connect(self.update_visibility)

        self.ui.viewCreatureCheck.mouseDoubleClickEvent = lambda a0: self.on_instance_visibility_double_click(self.ui.viewCreatureCheck)  # noqa: ARG005  # pyright: ignore[reportAttributeAccessIssue]
        self.ui.viewPlaceableCheck.mouseDoubleClickEvent = lambda a0: self.on_instance_visibility_double_click(self.ui.viewPlaceableCheck)  # noqa: ARG005  # pyright: ignore[reportAttributeAccessIssue]
        self.ui.viewDoorCheck.mouseDoubleClickEvent = lambda a0: self.on_instance_visibility_double_click(self.ui.viewDoorCheck)  # noqa: ARG005  # pyright: ignore[reportAttributeAccessIssue]
        self.ui.viewSoundCheck.mouseDoubleClickEvent = lambda a0: self.on_instance_visibility_double_click(self.ui.viewSoundCheck)  # noqa: ARG005  # pyright: ignore[reportAttributeAccessIssue]
        self.ui.viewTriggerCheck.mouseDoubleClickEvent = lambda a0: self.on_instance_visibility_double_click(self.ui.viewTriggerCheck)  # noqa: ARG005  # pyright: ignore[reportAttributeAccessIssue]
        self.ui.viewEncounterCheck.mouseDoubleClickEvent = lambda a0: self.on_instance_visibility_double_click(self.ui.viewEncounterCheck)  # noqa: ARG005  # pyright: ignore[reportAttributeAccessIssue]
        self.ui.viewWaypointCheck.mouseDoubleClickEvent = lambda a0: self.on_instance_visibility_double_click(self.ui.viewWaypointCheck)  # noqa: ARG005  # pyright: ignore[reportAttributeAccessIssue]
        self.ui.viewCameraCheck.mouseDoubleClickEvent = lambda a0: self.on_instance_visibility_double_click(self.ui.viewCameraCheck)  # noqa: ARG005  # pyright: ignore[reportAttributeAccessIssue]
        self.ui.viewStoreCheck.mouseDoubleClickEvent = lambda a0: self.on_instance_visibility_double_click(self.ui.viewStoreCheck)  # noqa: ARG005  # pyright: ignore[reportAttributeAccessIssue]

        # Undo/Redo
        self.ui.actionUndo.triggered.connect(lambda: self._controls.undo_stack.undo())
        self.ui.actionRedo.triggered.connect(lambda: self._controls.undo_stack.redo())

        # View
        self.ui.actionZoomIn.triggered.connect(lambda: self.ui.renderArea.camera.nudge_zoom(1))
        self.ui.actionZoomOut.triggered.connect(lambda: self.ui.renderArea.camera.nudge_zoom(-1))
        self.ui.actionRecentreCamera.triggered.connect(self.ui.renderArea.center_camera)
        self.ui.actionShowRoomBoundaries.toggled.connect(lambda value: setattr(self.ui.renderArea, "show_room_boundaries", value))
        self.ui.actionShowRoomBoundaries.toggled.connect(lambda _: self.ui.renderArea.update())
        self.ui.actionShowGrid.toggled.connect(lambda value: setattr(self.ui.renderArea, "show_grid", value))
        self.ui.actionShowGrid.toggled.connect(lambda _: self.ui.renderArea.update())
        # View -> Creature Labels
        self.ui.actionUseCreatureResRef.triggered.connect(lambda: setattr(self.settings, "creatureLabel", "resref"))
        self.ui.actionUseCreatureResRef.triggered.connect(self.update_visibility)
        self.ui.actionUseCreatureTag.triggered.connect(lambda: setattr(self.settings, "creatureLabel", "tag"))
        self.ui.actionUseCreatureTag.triggered.connect(self.update_visibility)
        self.ui.actionUseCreatureName.triggered.connect(lambda: setattr(self.settings, "creatureLabel", "name"))
        self.ui.actionUseCreatureName.triggered.connect(self.update_visibility)
        # View -> Door Labels
        self.ui.actionUseDoorResRef.triggered.connect(lambda: setattr(self.settings, "doorLabel", "resref"))
        self.ui.actionUseDoorResRef.triggered.connect(self.update_visibility)
        self.ui.actionUseDoorTag.triggered.connect(lambda: setattr(self.settings, "doorLabel", "tag"))
        self.ui.actionUseDoorTag.triggered.connect(self.update_visibility)
        self.ui.actionUseDoorName.triggered.connect(lambda: setattr(self.settings, "doorLabel", "name"))
        self.ui.actionUseDoorName.triggered.connect(self.update_visibility)
        # View -> Placeable Labels
        self.ui.actionUsePlaceableResRef.triggered.connect(lambda: setattr(self.settings, "placeableLabel", "resref"))
        self.ui.actionUsePlaceableResRef.triggered.connect(self.update_visibility)
        self.ui.actionUsePlaceableName.triggered.connect(lambda: setattr(self.settings, "placeableLabel", "name"))
        self.ui.actionUsePlaceableName.triggered.connect(self.update_visibility)
        self.ui.actionUsePlaceableTag.triggered.connect(lambda: setattr(self.settings, "placeableLabel", "tag"))
        self.ui.actionUsePlaceableTag.triggered.connect(self.update_visibility)
        # View -> Merchant Labels
        self.ui.actionUseMerchantResRef.triggered.connect(lambda: setattr(self.settings, "storeLabel", "resref"))
        self.ui.actionUseMerchantResRef.triggered.connect(self.update_visibility)
        self.ui.actionUseMerchantName.triggered.connect(lambda: setattr(self.settings, "storeLabel", "name"))
        self.ui.actionUseMerchantName.triggered.connect(self.update_visibility)
        self.ui.actionUseMerchantTag.triggered.connect(lambda: setattr(self.settings, "storeLabel", "tag"))
        self.ui.actionUseMerchantTag.triggered.connect(self.update_visibility)
        # View -> Sound Labels
        self.ui.actionUseSoundResRef.triggered.connect(lambda: setattr(self.settings, "soundLabel", "resref"))
        self.ui.actionUseSoundResRef.triggered.connect(self.update_visibility)
        self.ui.actionUseSoundName.triggered.connect(lambda: setattr(self.settings, "soundLabel", "name"))
        self.ui.actionUseSoundName.triggered.connect(self.update_visibility)
        self.ui.actionUseSoundTag.triggered.connect(lambda: setattr(self.settings, "soundLabel", "tag"))
        self.ui.actionUseSoundTag.triggered.connect(self.update_visibility)
        # View -> Waypoint Labels
        self.ui.actionUseWaypointResRef.triggered.connect(lambda: setattr(self.settings, "waypointLabel", "resref"))
        self.ui.actionUseWaypointResRef.triggered.connect(self.update_visibility)
        self.ui.actionUseWaypointName.triggered.connect(lambda: setattr(self.settings, "waypointLabel", "name"))
        self.ui.actionUseWaypointName.triggered.connect(self.update_visibility)
        self.ui.actionUseWaypointTag.triggered.connect(lambda: setattr(self.settings, "waypointLabel", "tag"))
        self.ui.actionUseWaypointTag.triggered.connect(self.update_visibility)
        # View -> Encounter Labels
        self.ui.actionUseEncounterResRef.triggered.connect(lambda: setattr(self.settings, "encounterLabel", "resref"))
        self.ui.actionUseEncounterResRef.triggered.connect(self.update_visibility)
        self.ui.actionUseEncounterName.triggered.connect(lambda: setattr(self.settings, "encounterLabel", "name"))
        self.ui.actionUseEncounterName.triggered.connect(self.update_visibility)
        self.ui.actionUseEncounterTag.triggered.connect(lambda: setattr(self.settings, "encounterLabel", "tag"))
        self.ui.actionUseEncounterTag.triggered.connect(self.update_visibility)
        # View -> Trigger Labels
        self.ui.actionUseTriggerResRef.triggered.connect(lambda: setattr(self.settings, "triggerLabel", "resref"))
        self.ui.actionUseTriggerResRef.triggered.connect(self.update_visibility)
        self.ui.actionUseTriggerTag.triggered.connect(lambda: setattr(self.settings, "triggerLabel", "tag"))
        self.ui.actionUseTriggerTag.triggered.connect(self.update_visibility)
        self.ui.actionUseTriggerName.triggered.connect(lambda: setattr(self.settings, "triggerLabel", "name"))
        self.ui.actionUseTriggerName.triggered.connect(self.update_visibility)

    def load(
        self,
        filepath: os.PathLike | str,
        resref: str,
        restype: ResourceType,
        data: bytes,
    ):
        """Load a resource from a file.

        GIT defaults (REVA): K1 LoadGIT 0x0050dd80 — UseTemplates/CurrentWeather/WeatherStarted ReadFieldBYTE 0;
        LoadProperties 0x00507490, CSWSAmbientSound::Load 0x005c95f0 (AreaProperties: AmbientSndDayVol/MusicDay/etc. INT 0);
        lists omit → empty. TSL Aspyr LoadGIT 0x0071ae10.

        Args:
        ----
            filepath: {Path or filename to load from}
            resref: {Unique identifier for the resource}
            restype: {The type of the resource}
            data: {The raw data of the resource}.

        Processing Logic:
        ----------------
            - Call super().load() to load base resource
            - Define search order for layout files
            - Load layout if found in search locations
            - Parse git data and call _loadGIT()
        """
        super().load(filepath, resref, restype, data)

        layout_data: bytes | None = None
        if self._installation is not None:
            order = [
                SearchLocation.OVERRIDE,
                SearchLocation.MODULES,
                SearchLocation.CHITIN,
            ]
            result: ResourceResult | None = self._installation.resource(resref, ResourceType.LYT, order)
            if result is not None:
                layout_data = result.data
        else:
            layout_data = self._resolve_path_resource(resref, "lyt", ("override_folder", "modules_folder"))

        if layout_data is not None:
            self._logger.debug("Found GITEditor layout for '%s'", filepath)
            self.load_layout(read_lyt(layout_data))
        else:
            self._logger.warning("Missing layout %s.lyt, needed for GITEditor '%s.%s'", resref, resref, restype)

        git = read_git(data)
        self._loadGIT(git)

    def _loadGIT(self, git: GIT):
        self._git = git
        self.ui.renderArea.set_git(self._git)
        self.ui.renderArea.center_camera()
        self._mode = _InstanceMode(self, self._installation, self._git)
        self.update_visibility()

    def build(self) -> tuple[bytes, bytes]:
        """Build GIT bytes.

        Write path (REVA): K1 SaveGIT 0x0050ba00 — UseTemplates 1; SaveProperties 0x00506090, CSWSAmbientSound::Save 0x005c96e0 (AreaProperties INT); lists per type. Omit OK.
        """
        return bytes_git(self._git), b""

    def new(self):
        super().new()

    def closeEvent(self, event: QCloseEvent):  # pyright: ignore[reportIncompatibleMethodOverride]
        # Skip confirmation dialog during testing to prevent access violations
        if "pytest" in sys.modules:
            event.accept()
            return

        from toolset.gui.common.localization import translate as tr

        reply = QMessageBox.question(
            self,
            tr("Confirm Exit"),
            tr("Really quit the GIT editor? You may lose unsaved changes."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            event.accept()  # Let the window close
        else:
            event.ignore()  # Ignore the close event

    def load_layout(self, layout: LYT):
        """Load layout walkmeshes into the UI renderer.

        Args:
        ----
            layout (LYT): Layout to load walkmeshes from

        Processing Logic:
        ----------------
            - Iterate through each room in the layout
            - Get the highest priority walkmesh asset for the room from the installation
            - If a walkmesh asset is found, read it and add it to a list
            - Set the list of walkmeshes on the UI renderer.
        """
        walkmeshes: list[BWM] = []
        for room in layout.rooms:
            walkmesh_data: bytes | None = None
            if self._installation is not None:
                order: list[SearchLocation] = [
                    SearchLocation.OVERRIDE,
                    SearchLocation.MODULES,
                    SearchLocation.CHITIN,
                ]
                walkmesh_resource: ResourceResult | None = self._installation.resource(
                    room.model,
                    ResourceType.WOK,
                    order,
                )
                walkmesh_data = walkmesh_resource.data if walkmesh_resource is not None else None
            else:
                walkmesh_data = self._resolve_path_resource(room.model, "wok", ("override_folder", "modules_folder"))

            if walkmesh_data is not None:
                try:
                    wok_data = read_bwm(walkmesh_data)
                except (ValueError, OSError):
                    self._logger.exception("Corrupted walkmesh cannot be loaded: '%s.wok'", room.model)
                else:
                    walkmeshes.append(wok_data)
            else:
                self._logger.warning("Missing walkmesh '%s.wok'", room.model)

        self._layout = layout
        self.ui.renderArea.set_walkmeshes(walkmeshes)
        self.ui.renderArea.set_layout(layout)

    def git(self) -> GIT:
        return self._git

    def set_mode(self, mode: _Mode):
        self._mode = mode

    def on_instance_visibility_double_click(self, checkbox: QCheckBox):
        """Toggles visibility of the relevant UI data on double click.

        Args:
        ----
            checkbox (QCheckBox): Checkbox for instance type visibility

        Processing Logic:
        ----------------
            - Uncheck all other instance type checkboxes
            - Check the checkbox that was double clicked
        """
        visibility_checkboxes: tuple[QCheckBox, ...] = (
            self.ui.viewCreatureCheck,
            self.ui.viewPlaceableCheck,
            self.ui.viewDoorCheck,
            self.ui.viewSoundCheck,
            self.ui.viewTriggerCheck,
            self.ui.viewEncounterCheck,
            self.ui.viewWaypointCheck,
            self.ui.viewCameraCheck,
            self.ui.viewStoreCheck,
        )
        set_exclusive_checkbox_selection(checkbox, visibility_checkboxes)

    def get_instance_external_name(self, instance: GITInstance) -> str | None:
        """Get external name of a GIT instance.

        Args:
        ----
            instance: The GIT instance object

        Returns:
        -------
            name: The external name of the instance or None

        Processing Logic:
        ----------------
            - Extract identifier from instance
            - Check if identifier is present in name buffer
            - If not present, get resource from installation using identifier
            - Extract name from resource data
            - Save name in buffer
            - Return name from buffer.
        """
        if self._installation is None:
            return None
        resid: ResourceIdentifier | None = instance.identifier()
        assert resid is not None, "resid cannot be None in get_instance_external_name({instance!r})"
        if resid not in self.name_buffer:
            res: ResourceResult | None = self._installation.resource(resid.resname, resid.restype)
            if res is None:
                return None
            self.name_buffer[resid] = self._installation.string(extract_name(res.data))
        return self.name_buffer[resid]

    def get_instance_external_tag(self, instance: GITInstance) -> str | None:
        if self._installation is None:
            return None
        res_ident: ResourceIdentifier | None = instance.identifier()
        assert res_ident is not None, f"resid cannot be None in get_instance_external_tag({instance!r})"
        if res_ident not in self.tag_buffer:
            res: ResourceResult | None = self._installation.resource(res_ident.resname, res_ident.restype)
            if res is None:
                return None
            self.tag_buffer[res_ident] = extract_tag_from_gff(res.data)
        return self.tag_buffer[res_ident]

    def enter_instance_mode(self):
        self._mode = _InstanceMode(self, self._installation, self._git)

    def enter_geometry_mode(self):
        self._mode = _GeometryMode(self, self._installation, self._git)

    def enter_spawn_mode(self):
        # Track which instance is being edited (encounters only).
        self._geom_instance = self.ui.renderArea.instance_selection.last()
        self._mode = _SpawnMode(self, self._installation, self._git)

    def move_camera_to_selection(self):
        instance = self.ui.renderArea.instance_selection.last()
        if not instance:
            self._logger.warning("No instance selected - moveCameraToSelection")
            return
        self.ui.renderArea.camera.set_position(instance.position.x, instance.position.y)

    # region Mode Calls
    def open_list_context_menu(self, item: QListWidgetItem, point: QPoint): ...

    def update_visibility(self):
        self._mode.update_visibility()

    def select_underneath(self):
        self._mode.select_underneath()

    def delete_selected(self, *, no_undo_stack: bool = False):
        self._mode.delete_selected(no_undo_stack=no_undo_stack)

    def duplicate_selected(self, position: Vector3):
        self._mode.duplicate_selected(position)

    def move_selected(self, x: float, y: float):
        self._mode.move_selected(x, y)

    def rotate_selected(self, angle: float):
        self._mode.rotate_selected(angle)

    def rotate_selected_to_point(self, x: float, y: float):
        self._mode.rotate_selected_to_point(x, y)

    def move_camera(self, x: float, y: float):
        self._mode.move_camera(x, y)

    def zoom_camera(self, amount: float):
        self._mode.zoom_camera(amount)

    def rotate_camera(self, angle: float):
        self._mode.rotate_camera(angle)

    # endregion

    # region Signal Callbacks
    def on_context_menu(self, point: QPoint):
        global_point: QPoint = self.ui.renderArea.mapToGlobal(point)
        world: Vector3 = self.ui.renderArea.to_world_coords(point.x(), point.y())
        self._mode.on_render_context_menu(Vector2.from_vector3(world), global_point)

    def on_filter_edited(self):
        self._mode.on_filter_edited(self.ui.filterEdit.text())

    def on_item_selection_changed(self):
        self._mode.on_item_selection_changed(self.ui.listWidget.currentItem())  # pyright: ignore[reportArgumentType]

    def on_item_context_menu(self, point: QPoint):
        global_point: QPoint = self.ui.listWidget.mapToGlobal(point)
        item: QListWidgetItem | None = self.ui.listWidget.currentItem()
        assert item is not None, f"item cannot be None in {self!r}.onItemContextMenu({point!r})"
        self._mode.open_list_context_menu(item, global_point)

    def on_mouse_moved(self, screen: Vector2, delta: Vector2, buttons: set[Qt.MouseButton], keys: set[Qt.Key]):
        world_delta: Vector2 = self.ui.renderArea.to_world_delta(delta.x, delta.y)
        world: Vector3 = self.ui.renderArea.to_world_coords(screen.x, screen.y)
        self._controls.on_mouse_moved(screen, delta, Vector2.from_vector3(world), world_delta, buttons, keys)
        self._mode.update_status_bar(Vector2.from_vector3(world))

    def on_mouse_scrolled(self, delta: Vector2, buttons: set[Qt.MouseButton], keys: set[Qt.Key]):
        self._controls.on_mouse_scrolled(delta, buttons, keys)

    def on_mouse_pressed(self, screen: Vector2, buttons: set[Qt.MouseButton], keys: set[Qt.Key]):
        self._controls.on_mouse_pressed(screen, buttons, keys)

    def on_mouse_released(self, buttons: set[Qt.MouseButton], keys: set[Qt.Key]):
        self._controls.on_mouse_released(Vector2(0, 0), buttons, keys)

    def on_marquee_select(self, world_rect: tuple[float, float, float, float], additive: bool):
        """Select instances inside the marquee world rect. Called from WalkmeshRenderer.sig_marquee_select."""
        min_x, min_y, max_x, max_y = world_rect
        in_rect: list[GITInstance] = []
        for instance in self._git.instances():
            if not self.ui.renderArea.is_instance_visible(instance):
                continue
            x, y = instance.position.x, instance.position.y
            if min_x <= x <= max_x and min_y <= y <= max_y:
                in_rect.append(instance)
        if additive:
            current = self._mode.renderer2d.instance_selection.all()
            combined = list({*current, *in_rect})
            self._mode.set_selection(combined)
        else:
            self._mode.set_selection(in_rect)

    def on_key_pressed(self, buttons: set[Qt.MouseButton], keys: set[Qt.Key]):
        self._controls.on_keyboard_pressed(buttons, keys)

    def keyPressEvent(self, e: QKeyEvent):  # pyright: ignore[reportIncompatibleMethodOverride]
        self.ui.renderArea.keyPressEvent(e)

    def keyReleaseEvent(self, e: QKeyEvent):  # pyright: ignore[reportIncompatibleMethodOverride]
        self.ui.renderArea.keyReleaseEvent(e)

    # endregion

if __name__ == "__main__":
    import sys

    from toolset.gui.editors.standalone import launch_editor_cli

    sys.exit(launch_editor_cli("git"))
