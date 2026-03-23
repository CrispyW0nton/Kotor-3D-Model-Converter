"""Editor window lifecycle: create, look up by path, and list open editors."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from toolset.gui.editor import Editor
from toolset.utils.window_base import add_window

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget

    from pykotor.resource.type import ResourceType

    pass


def _iter_editor_windows() -> list[Editor]:
    from toolset.utils.window import TOOLSET_WINDOWS

    return [window for window in TOOLSET_WINDOWS if isinstance(window, Editor)]


def _normalized_path(file_path: Path | str | None) -> Path | None:
    if file_path is None:
        return None
    path_obj = Path(file_path)
    return path_obj


def create_editor_window(
    filepath: Path | str | None = None,
    parent: QWidget | None = None,
) -> Editor:
    """Create a new editor window."""
    editor: Editor = Editor(parent)
    if filepath is not None:
        editor.load_file(filepath)
    add_window(editor)
    editor.show()
    return editor


def get_editor_by_filepath(filepath: Path | str) -> Editor | None:
    """Get an editor window by its filepath."""
    normalized_path: Path | None = _normalized_path(filepath)
    for window in _iter_editor_windows():
        if _normalized_path(window._filepath) == normalized_path:  # noqa: SLF001
            return window
    return None


def get_editor_by_resource_identity(
    filepath: Path | str,
    resname: str,
    restype: ResourceType,
) -> Editor | None:
    """Get an editor window by stable resource identity.

    Identity key is `(filepath, resname, restype)` to correctly disambiguate
    resources that may share the same container path.
    """
    normalized_path: Path | None = _normalized_path(filepath)
    normalized_resname: str = resname.strip().lower()

    for window in _iter_editor_windows():
        if _normalized_path(window._filepath) != normalized_path:  # noqa: SLF001
            continue
        if window._resname is None or window._restype is None:  # noqa: SLF001
            continue
        if window._resname.strip().lower() != normalized_resname:  # noqa: SLF001
            continue
        if window._restype != restype:  # noqa: SLF001
            continue
        return window

    return None


def get_editor_by_title(title: str) -> Editor | None:
    """Get an editor window by its title."""
    for window in _iter_editor_windows():
        if window.windowTitle() == title:
            return window
    return None


def get_all_editors() -> list[Editor]:
    """Get all editor windows."""
    return _iter_editor_windows()


def close_all_editors():
    """Close all editor windows."""
    for editor in get_all_editors():
        editor.close()
