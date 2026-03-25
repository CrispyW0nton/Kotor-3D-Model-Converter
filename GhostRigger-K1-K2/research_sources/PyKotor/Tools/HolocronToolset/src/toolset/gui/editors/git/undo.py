"""GIT editor undo: move, add/remove instance, and property change commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence, TypeVar

from qtpy.QtWidgets import QUndoCommand  # pyright: ignore[reportPrivateImportUsage]

from loggerplus import RobustLogger  # pyright: ignore[reportMissingTypeStubs]
from pykotor.resource.generics.git import (
    GITCamera,
    GITObject,
)
from toolset.gui.editors.git.git import GITEditor
from utility.common.geometry import Vector4

if TYPE_CHECKING:
    from pykotor.resource.generics.git import (
        GIT,
        GITEncounter,
        GITEncounterSpawnPoint,
        GITInstance,
    )
    from toolset.gui.editors.git.mode import _Mode
    from toolset.gui.windows.module_designer import ModuleDesigner
    from utility.common.geometry import Vector3


_T = TypeVar("_T")


def _select_instance_in_editor(
    editor: GITEditor | ModuleDesigner,
    instance: GITObject,
) -> None:
    """Select a single instance in either editor implementation."""
    if isinstance(editor, GITEditor):
        editor._mode.renderer2d.instance_selection.select([instance])  # noqa: SLF001
    else:
        editor.set_selection([instance])


def _rebuild_instance_list(editor: GITEditor | ModuleDesigner) -> None:
    """Refresh the editor instance list UI after undo/redo operations."""
    from toolset.gui.editors.git.mode import _InstanceMode

    if isinstance(editor, GITEditor):
        editor.enter_instance_mode()
        assert isinstance(editor._mode, _InstanceMode)  # noqa: SLF001
        editor._mode.build_list()  # noqa: SLF001
    else:
        editor.enter_instance_mode()
        editor.rebuild_instance_list()


def _instance_id_set(instances: Sequence[_T]) -> set[int]:
    """Build a fast identity set for repeated membership checks (any object type)."""
    return {id(instance) for instance in instances}


class MoveCommand(QUndoCommand):
    def __init__(
        self,
        instance: GITObject,
        old_position: Vector3,
        new_position: Vector3,
    ):
        RobustLogger().debug(f"Init movecommand with instance {instance.identifier()}")
        super().__init__()
        self.instance: GITObject = instance
        self.old_position: Vector3 = old_position
        self.new_position: Vector3 = new_position

    def undo(self):
        RobustLogger().debug(f"Undo position: {self.instance.identifier()} (NEW {self.new_position} --> {self.old_position})")
        self.instance.position = self.old_position

    def redo(self):
        RobustLogger().debug(f"Undo position: {self.instance.identifier()} ({self.old_position} --> NEW {self.new_position})")
        self.instance.position = self.new_position


class RotateCommand(QUndoCommand):
    def __init__(
        self,
        instance: GITObject,
        old_orientation: Vector4 | float,
        new_orientation: Vector4 | float,
    ):
        RobustLogger().debug(f"Init rotatecommand with instance: {instance.identifier()}")
        super().__init__()
        self.instance: GITObject = instance
        self.old_orientation: Vector4 | float = old_orientation
        self.new_orientation: Vector4 | float = new_orientation

    def undo(self):
        RobustLogger().debug(f"Undo rotation: {self.instance.identifier()} (NEW {self.new_orientation} --> {self.old_orientation})")
        if isinstance(self.instance, GITCamera):
            assert isinstance(self.old_orientation, Vector4)
            self.instance.orientation = self.old_orientation
        elif isinstance(self.instance, GITInstance):
            assert isinstance(self.old_orientation, float)
            self.instance.bearing = self.old_orientation
        else:
            raise ValueError(f"Invalid instance type: {self.instance.__class__.__name__}")

    def redo(self):
        RobustLogger().debug(f"Redo rotation: {self.instance.identifier()} ({self.old_orientation} --> NEW {self.new_orientation})")
        if isinstance(self.instance, GITCamera):
            assert isinstance(self.new_orientation, Vector4)
            self.instance.orientation = self.new_orientation
        elif isinstance(self.instance, GITInstance):
            assert isinstance(self.new_orientation, float)
            self.instance.bearing = self.new_orientation
        else:
            raise ValueError(f"Invalid instance type: {self.instance.__class__.__name__}")


class DuplicateCommand(QUndoCommand):
    def __init__(
        self,
        git: GIT,
        instances: Sequence[GITObject],
        editor: GITEditor | ModuleDesigner,
    ):
        super().__init__()
        self.git: GIT = git
        self.instances: list[GITObject] = list(instances)
        self.editor: GITEditor | ModuleDesigner = editor

    def undo(self):
        self.editor.enter_instance_mode()
        current_instance_ids: set[int] = _instance_id_set(self.git.instances())
        for instance in self.instances:
            if id(instance) not in current_instance_ids:
                RobustLogger().warning(f"{instance!r} not found in instances: no duplicate to undo.")
                continue
            RobustLogger().debug(f"Undo duplicate: {instance.identifier()}")
            _select_instance_in_editor(self.editor, instance)
            self.editor.delete_selected(no_undo_stack=True)
        self.rebuild_instance_list()

    def rebuild_instance_list(self):
        _rebuild_instance_list(self.editor)

    def redo(self):
        current_instance_ids: set[int] = _instance_id_set(self.git.instances())
        for instance in self.instances:
            if id(instance) in current_instance_ids:
                RobustLogger().warning(f"{instance!r} already found in instances: no duplicate to redo.")
                continue
            RobustLogger().debug(f"Redo duplicate: {instance.identifier()}")
            self.git.add(instance)
            _select_instance_in_editor(self.editor, instance)
        self.rebuild_instance_list()


class DeleteCommand(QUndoCommand):
    def __init__(
        self,
        git: GIT,
        instances: list[GITObject],
        editor: GITEditor | ModuleDesigner,
    ):
        super().__init__()
        self.git: GIT = git
        self.instances: list[GITObject] = instances
        self.editor: GITEditor | ModuleDesigner = editor

    def undo(self):
        RobustLogger().debug(f"Undo delete: {[repr(instance) for instance in self.instances]}")
        current_instance_ids: set[int] = _instance_id_set(self.git.instances())
        for instance in self.instances:
            if id(instance) in current_instance_ids:
                RobustLogger().warning(f"{instance!r} already found in instances: no deletecommand to undo.")
                continue
            self.git.add(instance)
        self.rebuild_instance_list()

    def rebuild_instance_list(self):
        _rebuild_instance_list(self.editor)

    def redo(self):
        RobustLogger().debug(f"Redo delete: {[repr(instance) for instance in self.instances]}")
        self.editor.enter_instance_mode()
        current_instance_ids: set[int] = _instance_id_set(self.git.instances())
        for instance in self.instances:
            if id(instance) not in current_instance_ids:
                RobustLogger().warning(f"{instance!r} not found in instances: no deletecommand to redo.")
                continue
            RobustLogger().debug(f"Redo delete: {instance!r}")
            _select_instance_in_editor(self.editor, instance)
            self.editor.delete_selected(no_undo_stack=True)
        self.rebuild_instance_list()


class InsertCommand(QUndoCommand):
    def __init__(
        self,
        git: GIT,
        instance: GITObject,
        editor: GITEditor | ModuleDesigner,
    ):
        super().__init__()
        self.git: GIT = git
        self.instance: GITObject = instance
        self._first_run: bool = True
        self.editor: GITEditor | ModuleDesigner = editor

    def undo(self):
        RobustLogger().debug(f"Undo insert: {self.instance.identifier()}")
        self.git.remove(self.instance)
        self.rebuild_instance_list()

    def rebuild_instance_list(self):
        from toolset.gui.editors.git.git import GITEditor
        from toolset.gui.editors.git.mode import _GeometryMode, _InstanceMode

        if isinstance(self.editor, GITEditor):
            old_mode: _Mode = self.editor._mode  # noqa: SLF001
            self.editor.enter_instance_mode()
            assert isinstance(self.editor._mode, _InstanceMode)  # noqa: SLF001
            self.editor._mode.build_list()  # noqa: SLF001
            if isinstance(old_mode, _GeometryMode):
                self.editor.enter_geometry_mode()
            elif isinstance(old_mode, self.editor._mode.__class__):  # _SpawnMode  # noqa: SLF001
                self.editor.enter_spawn_mode()
        else:
            self.editor.rebuild_instance_list()

    def redo(self):
        if self._first_run is True:
            RobustLogger().debug("Skipping first redo of InsertCommand.")
            self._first_run = False
            return
        RobustLogger().debug(f"Redo insert: {self.instance.identifier()}")
        self.git.add(self.instance)
        self.rebuild_instance_list()


def _refresh_git_views(editor: GITEditor | ModuleDesigner):
    if isinstance(editor, GITEditor):
        editor.ui.renderArea.update()
    else:
        editor.ui.flatRenderer.update()
        editor.ui.mainRenderer.update()


class SpawnPointInsertCommand(QUndoCommand):
    def __init__(
        self,
        encounter: GITEncounter,
        spawn: GITEncounterSpawnPoint,
        editor: GITEditor | ModuleDesigner,
    ):
        super().__init__()
        self.encounter: GITEncounter = encounter
        self.spawn: GITEncounterSpawnPoint = spawn
        self.editor: GITEditor | ModuleDesigner = editor

    def undo(self):
        spawn_ids = _instance_id_set(self.encounter.spawn_points)
        if id(self.spawn) in spawn_ids:
            self.encounter.spawn_points.remove(self.spawn)
        _refresh_git_views(self.editor)

    def redo(self):
        spawn_ids = _instance_id_set(self.encounter.spawn_points)
        if id(self.spawn) not in spawn_ids:
            self.encounter.spawn_points.append(self.spawn)
        _refresh_git_views(self.editor)


class SpawnPointDeleteCommand(QUndoCommand):
    def __init__(
        self,
        encounter: GITEncounter,
        spawn: GITEncounterSpawnPoint,
        editor: GITEditor | ModuleDesigner,
    ):
        super().__init__()
        self.encounter: GITEncounter = encounter
        self.spawn: GITEncounterSpawnPoint = spawn
        self.editor: GITEditor | ModuleDesigner = editor
        self.index: int = self._find_spawn_index(encounter, spawn)

    @staticmethod
    def _find_spawn_index(encounter: GITEncounter, spawn: GITEncounterSpawnPoint) -> int:
        try:
            return encounter.spawn_points.index(spawn)
        except ValueError:
            return -1

    @staticmethod
    def _insert_spawn(encounter: GITEncounter, spawn: GITEncounterSpawnPoint, index: int) -> None:
        if index < 0 or index > len(encounter.spawn_points):
            encounter.spawn_points.append(spawn)
            return
        encounter.spawn_points.insert(index, spawn)

    def undo(self):
        spawn_ids = _instance_id_set(self.encounter.spawn_points)
        if id(self.spawn) in spawn_ids:
            _refresh_git_views(self.editor)
            return
        self._insert_spawn(self.encounter, self.spawn, self.index)
        _refresh_git_views(self.editor)

    def redo(self):
        spawn_ids = _instance_id_set(self.encounter.spawn_points)
        if id(self.spawn) in spawn_ids:
            self.encounter.spawn_points.remove(self.spawn)
        _refresh_git_views(self.editor)


class SpawnPointMoveCommand(QUndoCommand):
    def __init__(
        self,
        spawn: GITEncounterSpawnPoint,
        old_position: Vector3,
        new_position: Vector3,
        editor: GITEditor | ModuleDesigner,
    ):
        super().__init__()
        self.spawn: GITEncounterSpawnPoint = spawn
        self.old_position: Vector3 = old_position
        self.new_position: Vector3 = new_position
        self.editor: GITEditor | ModuleDesigner = editor

    def undo(self):
        self.spawn.x = self.old_position.x
        self.spawn.y = self.old_position.y
        self.spawn.z = self.old_position.z
        _refresh_git_views(self.editor)

    def redo(self):
        self.spawn.x = self.new_position.x
        self.spawn.y = self.new_position.y
        self.spawn.z = self.new_position.z
        _refresh_git_views(self.editor)


class SpawnPointRotateCommand(QUndoCommand):
    def __init__(
        self,
        spawn: GITEncounterSpawnPoint,
        old_orientation: float,
        new_orientation: float,
        editor: GITEditor | ModuleDesigner,
    ):
        super().__init__()
        self.spawn: GITEncounterSpawnPoint = spawn
        self.old_orientation: float = old_orientation
        self.new_orientation: float = new_orientation
        self.editor: GITEditor | ModuleDesigner = editor

    def undo(self):
        self.spawn.orientation = self.old_orientation
        _refresh_git_views(self.editor)

    def redo(self):
        self.spawn.orientation = self.new_orientation
        _refresh_git_views(self.editor)
