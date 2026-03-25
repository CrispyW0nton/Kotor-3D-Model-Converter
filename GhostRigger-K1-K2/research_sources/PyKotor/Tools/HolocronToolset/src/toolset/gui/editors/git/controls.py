"""GIT editor controls: key bindings and mode switching."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import qtpy

from loggerplus import RobustLogger  # pyright: ignore[reportMissingTypeStubs]
from pykotor.resource.generics.git import (
    GITCamera,
    GITCreature,
    GITDoor,
    GITPlaceable,
    GITStore,
    GITWaypoint,
)
from toolset.data.misc import ControlItem
from toolset.gui.widgets.settings.editor_settings.git import GITSettings
from toolset.gui.widgets.settings.widgets.module_designer import ModuleDesignerSettings
from utility.common.geometry import Vector2, Vector3

if qtpy.QT5:
    from qtpy.QtWidgets import QUndoStack
elif qtpy.QT6:
    from qtpy.QtGui import QUndoStack

if TYPE_CHECKING:
    from qtpy.QtCore import Qt

    from pykotor.resource.generics.git import (
        GITInstance,
        GITObject,
    )
    from toolset.gui.editors.git.git import GITEditor
    from utility.common.geometry import Vector4


from toolset.gui.common.interaction.camera import calculate_zoom_strength
from toolset.gui.common.interaction.transforms import TransformInteractionState


class GITControlScheme:
    _ROTATABLE_INSTANCE_TYPES: tuple[type[GITObject], ...] = (
        GITCamera,
        GITCreature,
        GITDoor,
        GITPlaceable,
        GITStore,
        GITWaypoint,
    )

    def __init__(self, editor: GITEditor):
        self.editor: GITEditor = editor
        self.settings: GITSettings = GITSettings()

        self.undo_stack: QUndoStack = QUndoStack(self.editor)
        self.transform_state = TransformInteractionState(self.undo_stack, self.editor)

    def on_mouse_scrolled(
        self,
        delta: Vector2,
        buttons: set[Qt.MouseButton],
        keys: set[Qt.Key],
    ):
        if self.zoom_camera.satisfied(buttons, keys):
            if not delta.y:
                return  # sometimes it'll be zero when holding middlemouse-down.
            sens_setting: int = ModuleDesignerSettings().zoomCameraSensitivity2d
            zoom_factor = calculate_zoom_strength(delta.y, sens_setting)
            # RobustLogger.debug(f"on_mouse_scrolled zoom_camera (delta.y={delta.y}, zoom_factor={zoom_factor}, sensSetting={sensSetting}))")
            self.editor.zoom_camera(zoom_factor)

    def on_mouse_moved(
        self,
        screen: Vector2,
        screen_delta: Vector2,
        world: Vector2,
        world_delta: Vector2,
        buttons: set[Qt.MouseButton],
        keys: set[Qt.Key],
    ):
        # sourcery skip: extract-duplicate-method, remove-redundant-if, split-or-ifs
        from toolset.gui.editors.git.mode import _InstanceMode, _SpawnMode

        should_pan_camera: bool = self.pan_camera.satisfied(buttons, keys)
        should_rotate_camera: bool = self.rotate_camera.satisfied(buttons, keys)
        is_instance_mode: bool = isinstance(self.editor._mode, _InstanceMode)  # noqa: SLF001
        is_spawn_mode: bool = isinstance(self.editor._mode, _SpawnMode)  # noqa: SLF001

        # Adjust world_delta if cursor is locked
        adjusted_world_delta: Vector2 = world_delta
        if should_pan_camera or should_rotate_camera:
            self.editor.ui.renderArea.do_cursor_lock(screen)
            adjusted_world_delta = Vector2(-world_delta.x, -world_delta.y)

        if should_pan_camera:
            move_sens = ModuleDesignerSettings().moveCameraSensitivity2d / 100
            # RobustLogger.debug(f"on_mouse_scrolled move_camera (delta.y={screenDelta.y}, sensSetting={moveSens}))")
            self.editor.move_camera(-world_delta.x * move_sens, -world_delta.y * move_sens)
        if should_rotate_camera:
            self._handle_camera_rotation(screen_delta)

        if self.move_selected.satisfied(buttons, keys):
            if not self.transform_state.is_drag_moving and is_instance_mode:
                selection: list[GITObject] = self.editor._mode.renderer2d.instance_selection.all()  # noqa: SLF001
                self.transform_state.initial_positions = {instance: Vector3(*instance.position) for instance in selection}
                self.transform_state.is_drag_moving = True
            if not self.transform_state.is_drag_moving_spawn and is_spawn_mode:
                sp_selection = self.editor._mode.renderer2d.spawn_selection.all()  # noqa: SLF001
                self.transform_state.initial_spawn_positions = {sp_ref.spawn: Vector3(sp_ref.spawn.x, sp_ref.spawn.y, sp_ref.spawn.z) for sp_ref in sp_selection}
                self.transform_state.is_drag_moving_spawn = True
            self.editor.move_selected(adjusted_world_delta.x, adjusted_world_delta.y)
        if self.rotate_selected_to_point.satisfied(buttons, keys):
            if not self.transform_state.is_drag_rotating and not self.editor.ui.lockInstancesCheck.isChecked() and is_instance_mode:
                self.transform_state.is_drag_rotating = True
                RobustLogger().debug("rotateSelected instance in GITControlScheme")
                selection = self.editor._mode.renderer2d.instance_selection.all()  # noqa: SLF001
                for instance in selection:
                    if not self._is_rotatable_instance(instance):
                        continue  # doesn't support rotations.
                    self.transform_state.initial_rotations[instance] = self._get_instance_rotation(instance)
            if not self.transform_state.is_drag_rotating_spawn and is_spawn_mode:
                sp_selection = self.editor._mode.renderer2d.spawn_selection.all()  # noqa: SLF001
                self.transform_state.initial_spawn_rotations = {sp_ref.spawn: float(sp_ref.spawn.orientation) for sp_ref in sp_selection}
                self.transform_state.is_drag_rotating_spawn = True
            self.editor.rotate_selected_to_point(world.x, world.y)

    @staticmethod
    def _is_rotatable_instance(instance: GITObject) -> bool:
        """Return whether this instance supports rotation editing."""
        return isinstance(instance, GITControlScheme._ROTATABLE_INSTANCE_TYPES)

    @staticmethod
    def _get_instance_rotation(instance: GITInstance) -> float | Vector4:
        """Return the current rotation payload for transform-undo capture."""
        if isinstance(instance, GITCamera):
            return instance.orientation
        return instance.bearing

    def _handle_camera_rotation(self, screen_delta: Vector2):
        delta_magnitude = abs(screen_delta.x)
        direction = -1 if screen_delta.x < 0 else 1 if screen_delta.x > 0 else 0
        rotate_sens = ModuleDesignerSettings().rotateCameraSensitivity2d / 1000
        rotate_amount = delta_magnitude * rotate_sens * direction
        # RobustLogger.debug(f"on_mouse_scrolled rotate_camera (delta_value={delta_magnitude}, rotateAmount={rotateAmount}, sensSetting={rotateSens}))")
        self.editor.rotate_camera(rotate_amount)

    def handle_undo_redo_from_long_action_finished(self):
        self.transform_state.finalize_undo_actions()

    def on_mouse_pressed(self, screen: Vector2, buttons: set[Qt.MouseButton], keys: set[Qt.Key]):
        if self.duplicate_selected.satisfied(buttons, keys):
            position = self.editor.ui.renderArea.to_world_coords(screen.x, screen.y)
            self.editor.duplicate_selected(position)
        elif self.select_underneath.satisfied(buttons, keys):
            if self.editor.ui.renderArea.instances_under_mouse():
                self.editor.select_underneath()
            else:
                self.editor.ui.renderArea.start_marquee(screen)

    def on_mouse_released(
        self,
        screen: Vector2,
        buttons: set[Qt.MouseButton],
        keys: set[Qt.Key],
    ):
        self.handle_undo_redo_from_long_action_finished()

    def on_keyboard_pressed(
        self,
        buttons: set[Qt.MouseButton],
        keys: set[Qt.Key],
    ):
        from toolset.gui.editors.git.mode import _InstanceMode, _SpawnMode
        from toolset.gui.editors.git.undo import DeleteCommand, SpawnPointDeleteCommand

        if self.delete_selected.satisfied(buttons, keys):
            is_instance_mode = isinstance(self.editor._mode, _InstanceMode)  # noqa: SLF001
            is_spawn_mode = isinstance(self.editor._mode, _SpawnMode)  # noqa: SLF001
            if is_instance_mode:
                selection = self.editor._mode.renderer2d.instance_selection.all()  # noqa: SLF001
                if isinstance(selection, list):
                    self.undo_stack.push(DeleteCommand(self.editor._git, cast("list[GITObject]", selection.copy()), self.editor))  # noqa: SLF001
            elif is_spawn_mode:
                sp_ref = self.editor._mode.renderer2d.spawn_selection.last()  # noqa: SLF001
                if sp_ref is not None and sp_ref.spawn in sp_ref.encounter.spawn_points:
                    self.undo_stack.push(SpawnPointDeleteCommand(sp_ref.encounter, sp_ref.spawn, self.editor))
            self.editor.delete_selected(no_undo_stack=True)

        if self.toggle_instance_lock.satisfied(buttons, keys):
            self.editor.ui.lockInstancesCheck.setChecked(not self.editor.ui.lockInstancesCheck.isChecked())

    def on_keyboard_released(
        self,
        buttons: set[Qt.MouseButton],
        keys: set[Qt.Key],
    ):
        self.handle_undo_redo_from_long_action_finished()

    # Use @property decorators to allow users to change settings without restarting the editor.
    @property
    def pan_camera(self) -> ControlItem:
        return ControlItem(self.settings.moveCameraBind)

    @property
    def rotate_camera(self) -> ControlItem:
        return ControlItem(self.settings.rotateCameraBind)

    @property
    def zoom_camera(self) -> ControlItem:
        return ControlItem(self.settings.zoomCameraBind)

    @property
    def rotate_selected_to_point(self) -> ControlItem:
        return ControlItem(self.settings.rotateSelectedToPointBind)

    @property
    def move_selected(self) -> ControlItem:
        return ControlItem(self.settings.moveSelectedBind)

    @property
    def select_underneath(self) -> ControlItem:
        return ControlItem(self.settings.selectUnderneathBind)

    @property
    def delete_selected(self) -> ControlItem:
        return ControlItem(self.settings.deleteSelectedBind)

    @property
    def duplicate_selected(self) -> ControlItem:
        return ControlItem(self.settings.duplicateSelectedBind)

    @property
    def toggle_instance_lock(self) -> ControlItem:
        return ControlItem(self.settings.toggleLockInstancesBind)
