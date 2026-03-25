"""Transform interaction: drag move/rotate state and QUndoStack integration for GIT editors."""

from __future__ import annotations

from typing import TYPE_CHECKING

import qtpy

if qtpy.QT5:
    from qtpy.QtWidgets import QUndoStack
elif qtpy.QT6:
    pass

from loggerplus import RobustLogger  # pyright: ignore[reportMissingTypeStubs]
from pykotor.resource.generics.git import GITCamera
from utility.common.geometry import Vector3

if TYPE_CHECKING:
    from qtpy.QtGui import QUndoStack

    from pykotor.resource.generics.git import GITEncounterSpawnPoint, GITObject
    from utility.common.geometry import Vector4


class TransformInteractionState:
    """
    Manages the drag-and-drop transformation state and finalizing changes into QUndoStack commands
    shared across different generic interface views like Module Designer and GIT Editor.
    """

    def __init__(self, undo_stack: QUndoStack, editor=None):
        self.undo_stack: QUndoStack = undo_stack
        self.editor = editor  # Used for spawn point references in the older systems

        self.initial_positions: dict[GITObject, Vector3] = {}
        self.initial_rotations: dict[GITObject, Vector4 | float] = {}
        self.initial_spawn_positions: dict[GITEncounterSpawnPoint, Vector3] = {}
        self.initial_spawn_rotations: dict[GITEncounterSpawnPoint, float] = {}

        self.is_drag_moving: bool = False
        self.is_drag_rotating: bool = False
        self.is_drag_moving_spawn: bool = False
        self.is_drag_rotating_spawn: bool = False

    def reset_state(self):
        self.initial_positions.clear()
        self.initial_rotations.clear()
        self.initial_spawn_positions.clear()
        self.initial_spawn_rotations.clear()

        self.is_drag_moving = False
        self.is_drag_rotating = False
        self.is_drag_moving_spawn = False
        self.is_drag_rotating_spawn = False

    def finalize_undo_actions(self):
        """
        Commits active transforms to the undo stack. To be called on mouse release.
        """
        from toolset.gui.editors.git.undo import (
            MoveCommand,
            RotateCommand,
            SpawnPointMoveCommand,
            SpawnPointRotateCommand,
        )

        # Check if we were dragging generic instances
        if self.is_drag_moving:
            for instance, old_position in self.initial_positions.items():
                new_position = instance.position
                if old_position and new_position != old_position:
                    RobustLogger().debug("TransformInteractionState: Pushing MoveCommand")
                    self.undo_stack.push(MoveCommand(instance, old_position, new_position))
                elif not old_position:
                    RobustLogger().debug(f"No old position for {instance.resref}")
                else:
                    RobustLogger().debug(f"TransformInteractionState: Positions identical - no MoveCommand for {instance.resref}")

            self.initial_positions.clear()
            self.is_drag_moving = False

        # Rotating generic instances
        if self.is_drag_rotating:
            for instance, old_rotation in self.initial_rotations.items():
                new_rotation = instance.orientation if isinstance(instance, GITCamera) else instance.bearing
                if old_rotation and new_rotation != old_rotation:
                    RobustLogger().debug("TransformInteractionState: Pushing RotateCommand")
                    self.undo_stack.push(RotateCommand(instance, old_rotation, new_rotation))
                elif not old_rotation:
                    RobustLogger().debug(f"No old rotation for {instance.resref}")
                else:
                    RobustLogger().debug(f"TransformInteractionState: Rotations identical - no RotateCommand for {instance.resref}")

            self.initial_rotations.clear()
            self.is_drag_rotating = False

        # Spawn point movement
        if self.is_drag_moving_spawn and self.editor is not None:
            for spawn, old_pos in self.initial_spawn_positions.items():
                new_pos = Vector3(spawn.x, spawn.y, spawn.z)
                if new_pos != old_pos:
                    self.undo_stack.push(SpawnPointMoveCommand(spawn, old_pos, new_pos, self.editor))

            self.initial_spawn_positions.clear()
            self.is_drag_moving_spawn = False

        # Spawn point rotating
        if self.is_drag_rotating_spawn and self.editor is not None:
            for spawn, old_rot in self.initial_spawn_rotations.items():
                new_rot = float(spawn.orientation)
                if new_rot != old_rot:
                    self.undo_stack.push(SpawnPointRotateCommand(spawn, old_rot, new_rot, self.editor))

            self.initial_spawn_rotations.clear()
            self.is_drag_rotating_spawn = False
