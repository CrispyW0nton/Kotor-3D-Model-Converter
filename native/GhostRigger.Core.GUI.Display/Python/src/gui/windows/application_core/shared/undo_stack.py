"""Global undo/redo stack for scene-level edits.

The viewport already keeps its own lightweight transform undo/redo history
(see ``viewport_core/widgets/history_animation.py``). This module provides a
*higher-level*, object-oriented command stack that can also record lighting
and camera edits and any future scene operation.

The main window instantiates :class:`SceneUndoStack` as
``self._scene_undo_stack``. The existing Ctrl+Z / Ctrl+Shift+Z shortcuts first
consult the viewport's undo stack; when it is empty they fall through to this
scene-level stack (see ``window_chrome.py``).
"""

from __future__ import annotations

from typing import Callable, Optional

try:
    from PySide6 import QtCore
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc


class SceneEditCommand:
    """Base class for an undoable / redoable scene edit.

    Subclasses implement :meth:`undo` and :meth:`redo`. :meth:`merge_with`
    optionally coalesces consecutive commands of the same type so that, for
    example, a stream of transform drags collapses into a single entry.
    """

    label: str = "Edit"

    def undo(self) -> None:
        raise NotImplementedError

    def redo(self) -> None:
        raise NotImplementedError

    def merge_with(self, other: "SceneEditCommand") -> bool:
        """Attempt to merge *other* into this command.

        Return ``True`` if the merge succeeded (so *other* is discarded) or
        ``False`` to keep *other* as a separate stack entry.
        """
        return False


class TransformEditCommand(SceneEditCommand):
    """An undoable transform change for a single scene node."""

    label = "Transform"

    def __init__(
        self,
        node_id: object,
        old_transform,
        new_transform,
        apply_fn: Callable[[object, object], None],
        *,
        label: str = "Transform",
    ) -> None:
        self.node_id = node_id
        self.old_transform = tuple(old_transform)
        self.new_transform = tuple(new_transform)
        self.apply_fn = apply_fn
        self.label = label

    def undo(self) -> None:
        self.apply_fn(self.node_id, self.old_transform)

    def redo(self) -> None:
        self.apply_fn(self.node_id, self.new_transform)

    def merge_with(self, other: "SceneEditCommand") -> bool:
        if not isinstance(other, TransformEditCommand):
            return False
        if other.node_id != self.node_id:
            return False
        # Only merge if the other command continues the same drag (its "old"
        # matches our "new"). Otherwise they are independent operations.
        if tuple(other.old_transform) != tuple(self.new_transform):
            return False
        self.new_transform = tuple(other.new_transform)
        return True


class LightingEditCommand(SceneEditCommand):
    """An undoable lighting change."""

    label = "Lighting"

    def __init__(
        self,
        target_id: object,
        old_payload,
        new_payload,
        apply_fn: Callable[[object, object], None],
        *,
        label: str = "Lighting",
    ) -> None:
        self.target_id = target_id
        self.old_payload = old_payload
        self.new_payload = new_payload
        self.apply_fn = apply_fn
        self.label = label

    def undo(self) -> None:
        self.apply_fn(self.target_id, self.old_payload)

    def redo(self) -> None:
        self.apply_fn(self.target_id, self.new_payload)


class CameraEditCommand(SceneEditCommand):
    """An undoable camera change."""

    label = "Camera"

    def __init__(
        self,
        camera_id: object,
        old_state,
        new_state,
        apply_fn: Callable[[object, object], None],
        *,
        label: str = "Camera",
    ) -> None:
        self.camera_id = camera_id
        self.old_state = old_state
        self.new_state = new_state
        self.apply_fn = apply_fn
        self.label = label

    def undo(self) -> None:
        self.apply_fn(self.camera_id, self.old_state)

    def redo(self) -> None:
        self.apply_fn(self.camera_id, self.new_state)


class SceneUndoStack(QtCore.QObject):
    """A bounded undo/redo command stack with Qt signals.

    Use :meth:`push` to apply a command (it is immediately ``redo``ne). Use
    :meth:`undo` / :meth:`redo` to navigate. The ``can_undo_changed`` and
    ``can_redo_changed`` signals let actions / menu items keep their enabled
    state in sync.
    """

    can_undo_changed = QtCore.Signal(bool)
    can_redo_changed = QtCore.Signal(bool)
    clean_changed = QtCore.Signal(bool)  # emitted when "clean" boundary changes

    def __init__(self, max_size: int = 100, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._undo_stack: list[SceneEditCommand] = []
        self._redo_stack: list[SceneEditCommand] = []
        self._max_size = max_size
        self._clean_index = 0  # number of commands considered "saved"
        self._suspend_signals = False

    # -- queries -----------------------------------------------------------

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def count(self) -> int:
        return len(self._undo_stack)

    def redo_count(self) -> int:
        return len(self._redo_stack)

    def undo_text(self) -> str:
        if not self._undo_stack:
            return ""
        return self._undo_stack[-1].label

    def redo_text(self) -> str:
        if not self._redo_stack:
            return ""
        return self._redo_stack[-1].label

    # -- mutation ----------------------------------------------------------

    def push(self, command: SceneEditCommand) -> None:
        """Apply *command* (redo) and push it onto the undo stack.

        If the previous command on the stack merges with *command* the two are
        coalesced instead of creating a new entry.
        """
        if self._undo_stack:
            top = self._undo_stack[-1]
            if top.merge_with(command):
                self._redo_stack.clear()
                self._emit_signals()
                return
        command.redo()
        self._undo_stack.append(command)
        self._redo_stack.clear()
        if len(self._undo_stack) > self._max_size:
            dropped = self._undo_stack.pop(0)
            self._clean_index = max(0, self._clean_index - 1)
            del dropped
        self._emit_signals()

    def undo(self) -> Optional[SceneEditCommand]:
        if not self._undo_stack:
            return None
        command = self._undo_stack.pop()
        command.undo()
        self._redo_stack.append(command)
        self._emit_signals()
        return command

    def redo(self) -> Optional[SceneEditCommand]:
        if not self._redo_stack:
            return None
        command = self._redo_stack.pop()
        command.redo()
        self._undo_stack.append(command)
        if len(self._undo_stack) > self._max_size:
            dropped = self._undo_stack.pop(0)
            self._clean_index = max(0, self._clean_index - 1)
            del dropped
        self._emit_signals()
        return command

    def clear(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._clean_index = 0
        self._emit_signals()

    def set_max_size(self, max_size: int) -> None:
        self._max_size = max(1, max_size)
        while len(self._undo_stack) > self._max_size:
            dropped = self._undo_stack.pop(0)
            self._clean_index = max(0, self._clean_index - 1)
            del dropped
        self._emit_signals()

    def set_clean(self) -> None:
        """Mark the current position as the saved/clean state."""
        self._clean_index = len(self._undo_stack)
        self._emit_signals()

    def is_clean(self) -> bool:
        return self._clean_index == len(self._undo_stack)

    # -- internal ----------------------------------------------------------

    def _emit_signals(self) -> None:
        if self._suspend_signals:
            return
        self.can_undo_changed.emit(self.can_undo())
        self.can_redo_changed.emit(self.can_redo())
        self.clean_changed.emit(self.is_clean())
