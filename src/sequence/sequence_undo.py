"""Small command-style undo stack for sequence asset edits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class SequenceCommand:
    label: str
    undo: Callable[[], None]
    redo: Callable[[], None]


class SequenceUndoStack:
    def __init__(self, limit: int = 100) -> None:
        self.limit = int(limit)
        self.undo_stack: list[SequenceCommand] = []
        self.redo_stack: list[SequenceCommand] = []

    def push(self, command: SequenceCommand, *, run: bool = False) -> None:
        if run:
            command.redo()
        self.undo_stack.append(command)
        if len(self.undo_stack) > self.limit:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self) -> bool:
        if not self.undo_stack:
            return False
        command = self.undo_stack.pop()
        command.undo()
        self.redo_stack.append(command)
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False
        command = self.redo_stack.pop()
        command.redo()
        self.undo_stack.append(command)
        return True
