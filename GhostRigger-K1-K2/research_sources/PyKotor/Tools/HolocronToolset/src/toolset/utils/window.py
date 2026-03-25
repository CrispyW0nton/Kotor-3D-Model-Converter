"""Window registry: keep toolset windows alive, recent files, and open-resource helpers."""

from __future__ import annotations

import os

from functools import singledispatch
from pathlib import Path
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QMainWindow, QMessageBox, QWidget

from loggerplus import RobustLogger  # type: ignore[import-untyped]
from pykotor.extract.file import FileResource  # type: ignore[import-not-found]
from pykotor.resource.type import ResourceType  # type: ignore[import-not-found]
from toolset.gui.common.localization import translate as tr, trf  # type: ignore[import-not-found]
from toolset.gui.widgets.settings.installations import GlobalSettings  # type: ignore[import-not-found]

if TYPE_CHECKING:
    from qtpy.QtGui import QCloseEvent
    from qtpy.QtWidgets import QDialog, QMainWindow

    from toolset.data.installation import HTInstallation
    from toolset.gui.editor import Editor

TOOLSET_WINDOWS: list[QDialog | QMainWindow] = []
_UNIQUE_SENTINEL = object()
_MAX_RECENT_FILES = 15
_TOP_LEVEL_MESSAGE_FLAGS = (
    Qt.WindowType.Window
    | Qt.WindowType.Dialog
    | Qt.WindowType.WindowStaysOnTopHint
)  # pyright: ignore[reportArgumentType]
_IMAGE_OR_TEXTURE_CATEGORY = {"Images", "Textures"}


def _normalize_recent_files(entries: list[str]) -> list[str]:
    """Return a deduplicated list of existing file paths as strings."""
    seen: set[Path] = set()
    recent_files: list[str] = []
    for value in entries:
        path = Path(value)
        if path.is_file() and path not in seen:
            seen.add(path)
            recent_files.append(str(path))
    return recent_files


def _prepend_recent_file(file: Path | str, recent_files: list[str]) -> list[str]:
    """Update a normalized recent-files list with file at the head."""
    path_text = str(file)
    filtered: list[str] = [value for value in recent_files if value != path_text]
    filtered.insert(0, path_text)
    return filtered[:_MAX_RECENT_FILES]


def add_window(
    window: QDialog | QMainWindow,
    *,
    show: bool = True,
):
    """Prevents Qt's garbage collection by keeping a reference to the window."""
    original_closeEvent = window.closeEvent

    def new_close_event(
        event: QCloseEvent | None = _UNIQUE_SENTINEL,  # type: ignore[assignment]  # pyright: ignore[reportArgumentType]
        *args,
        **kwargs,
    ):
        from toolset.gui.editor import Editor

        if isinstance(window, Editor) and window._filepath is not None:  # noqa: SLF001
            add_recent_file(window._filepath)  # noqa: SLF001
        if window in TOOLSET_WINDOWS:
            RobustLogger().debug(f"Removing window (normal): {window.__class__.__name__} ({window})")
            TOOLSET_WINDOWS.remove(window)
        if event is _UNIQUE_SENTINEL:  # Make event arg optional just in case the class has the wrong definition.
            RobustLogger().debug(f"Closing window (sentinel): {window.__class__.__name__} ({window})")
            original_closeEvent(*args, **kwargs)
        else:
            RobustLogger().debug(f"Closing window (event): {window.__class__.__name__} ({window})")
            original_closeEvent(event, *args, **kwargs)  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]

    window.closeEvent = new_close_event  # type: ignore[assignment]  # pyright: ignore[reportAttributeAccessIssue]
    RobustLogger().debug(f"Adding window (normal): {window.__class__.__name__} ({window})")
    if show:
        window.show()
    TOOLSET_WINDOWS.append(window)


def add_recent_file(file: Path) -> None:
    """Update the list of recent files (deduplicated, order preserved)."""
    settings = GlobalSettings()
    recent_files = _normalize_recent_files(settings.recentFiles)
    recent_files = _prepend_recent_file(file, recent_files)
    settings.recentFiles = recent_files


@singledispatch
def open_resource_editor(  # noqa: PLR0913
    resource_or_path: FileResource | os.PathLike | str,
    installation: HTInstallation | None = None,
    parent_window: QWidget | None = None,
    *,
    gff_specialized: bool | None = None,
    resname: str | None = None,
    restype: ResourceType | None = None,
    data: bytes | None = None,
    open_as_generic_gff: bool = False,
) -> tuple[os.PathLike | str | None, Editor | QMainWindow | None]:
    raise NotImplementedError("Unsupported input type")


@open_resource_editor.register(FileResource)
def _(
    resource: FileResource,
    installation: HTInstallation | None = None,
    parent_window: QWidget | None = None,
    *,
    gff_specialized: bool | None = None,
    open_as_generic_gff: bool = False,
    **kwargs,
) -> tuple[os.PathLike | str | None, Editor | QMainWindow | None]:
    # Implementation for FileResource
    return _open_resource_editor_impl(
        resource=resource,
        installation=installation,
        parent_window=parent_window,
        gff_specialized=gff_specialized,
        open_as_generic_gff=open_as_generic_gff,
    )


@open_resource_editor.register(str)
@open_resource_editor.register(os.PathLike)
def _(  # noqa: PLR0913
    path: os.PathLike | str,
    resname: str,
    restype: ResourceType,
    data: bytes,
    installation: HTInstallation | None = None,
    parent_window: QWidget | None = None,
    *,
    gff_specialized: bool | None = None,
    open_as_generic_gff: bool = False,
) -> tuple[os.PathLike | str | None, Editor | QMainWindow | None]:
    return _open_resource_editor_impl(
        filepath=path,
        resname=resname,
        restype=restype,
        data=data,
        installation=installation,
        parent_window=parent_window,
        gff_specialized=gff_specialized,
        open_as_generic_gff=open_as_generic_gff,
    )


def _open_resource_editor_impl(  # noqa: C901, PLR0913, PLR0912, PLR0915
    resource: FileResource | None = None,
    filepath: os.PathLike | str | None = None,
    resname: str | None = None,
    restype: ResourceType | None = None,
    data: bytes | None = None,
    installation: HTInstallation | None = None,
    parent_window: QWidget | None = None,
    gff_specialized: bool | None = None,
    open_as_generic_gff: bool = False,
) -> tuple[os.PathLike | str | None, Editor | QMainWindow | None]:
    # To avoid circular imports, these need to be placed within the function
    from toolset.gui.editors.are import AREEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.bwm import BWMEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.dlg import DLGEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.erf import ERFEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.fac import FACEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.gff import GFFEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.git import GITEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.ifo import IFOEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.jrl import JRLEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.lip import LIPEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.ltr import LTREditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.mdl import MDLEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.nss import NSSEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.pth import PTHEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.ssf import SSFEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.tlk import TLKEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.tpc import TPCEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.twoda import TwoDAEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.txt import TXTEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.utc import UTCEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.utd import UTDEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.ute import UTEEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.uti import UTIEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.utm import UTMEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.utp import UTPEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.uts import UTSEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.utt import UTTEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.utw import UTWEditor  # type: ignore[import-not-found] # noqa: PLC0415
    from toolset.gui.editors.wav import WAVEditor  # type: ignore[import-not-found] # noqa: PLC0415

    if gff_specialized is None:
        gff_specialized = GlobalSettings().gffSpecializedEditors
    if open_as_generic_gff:
        gff_specialized = False

    editor: Editor | None = None
    parent_window_widget: QWidget | None = parent_window if isinstance(parent_window, QWidget) else None

    if resource:
        try:
            data = resource.data()
        except Exception:  # noqa: BLE001
            RobustLogger().exception("Exception occurred in _open_resource_editor_impl")
            from toolset.gui.helpers.message_box import show_error_message
            show_error_message(tr("Failed to get the file data."), tr("An error occurred while attempting to read the data of the file."))
            return None, None
        restype = resource.restype()
        resname = resource.resname()
        filepath = resource.filepath()
    elif resname and resname.strip() and restype and data is not None and filepath:
        ...
    else:
        raise ValueError("Invalid input combination")

    from toolset.utils.window_editor import get_editor_by_resource_identity

    existing_editor = get_editor_by_resource_identity(filepath, resname, restype)
    if existing_editor is not None:
        try:
            existing_editor.show()
            existing_editor.raise_()
            existing_editor.activateWindow()
        except Exception:  # noqa: BLE001
            RobustLogger().exception(
                "Failed to focus existing editor for '%s.%s' (filepath=%s)",
                resname,
                restype,
                filepath,
            )
        return filepath, existing_editor

    def _instantiate_editor(editor_class: type[Editor], *, requires_installation: bool = False) -> Editor | None:
        """Create an editor instance with optional installation requirements."""
        if requires_installation and installation is None:
            return None
        return editor_class(None, installation)

    # Mapping of resource types to editor creation functions
    # Each entry is a tuple: (editor_class, requires_installation)
    editor_mappings: dict[ResourceType, tuple[type[Editor], bool]] = {
        # Simple mappings (no special conditions)
        ResourceType.TwoDA: (TwoDAEditor, False),
        ResourceType.SSF: (SSFEditor, False),
        ResourceType.TLK: (TLKEditor, False),
        ResourceType.LTR: (LTREditor, False),
        ResourceType.LIP: (LIPEditor, False),
        ResourceType.NSS: (NSSEditor, False),
        ResourceType.GUI: (GFFEditor, False),
    }

    # Category-based mappings
    if restype.category == "Walkmeshes":
        editor = _instantiate_editor(BWMEditor)
    elif restype.category in _IMAGE_OR_TEXTURE_CATEGORY and restype != ResourceType.TXI:
        editor = _instantiate_editor(TPCEditor)
    elif restype.category == "Audio":
        editor = _instantiate_editor(WAVEditor)
    elif restype.name in (ResourceType.ERF, ResourceType.SAV, ResourceType.MOD, ResourceType.RIM, ResourceType.BIF):
        editor = _instantiate_editor(ERFEditor)
    elif restype == ResourceType.NCS:
        if installation is None:
            QMessageBox.warning(
                parent_window_widget,
                tr("Cannot decompile NCS without an installation active"),
                tr("Please select an installation from the dropdown before loading an NCS."),
            )
            return None, None
        editor = _instantiate_editor(NSSEditor)
    elif restype == ResourceType.BIK:
        from toolset.gui.helpers.message_box import show_info_message
        show_info_message(tr("Unsupported file type"), tr("BIK video preview is not supported yet in the Toolset editor."), parent_window_widget)
        return None, None
    else:
        # Handle target_type mappings with GFF specialization logic
        target_type = restype.target_type()
        gff_editor_mappings = {
            ResourceType.DLG: DLGEditor,
            ResourceType.UTC: UTCEditor,
            ResourceType.BTC: UTCEditor,
            ResourceType.BIC: UTCEditor,
            ResourceType.UTP: UTPEditor,
            ResourceType.BTP: UTPEditor,
            ResourceType.UTD: UTDEditor,
            ResourceType.BTD: UTDEditor,
            ResourceType.IFO: IFOEditor,
            ResourceType.UTS: UTSEditor,
            ResourceType.UTT: UTTEditor,
            ResourceType.BTT: UTTEditor,
            ResourceType.UTM: UTMEditor,
            ResourceType.BTM: UTMEditor,
            ResourceType.UTW: UTWEditor,
            ResourceType.UTE: UTEEditor,
            ResourceType.BTE: UTEEditor,
            ResourceType.UTI: UTIEditor,
            ResourceType.BTI: UTIEditor,
            ResourceType.JRL: JRLEditor,
            ResourceType.ARE: AREEditor,
            ResourceType.PTH: PTHEditor,
            ResourceType.GIT: GITEditor,
            ResourceType.FAC: FACEditor,
        }

        if target_type in gff_editor_mappings:
            specialized_editor_class = gff_editor_mappings[target_type]
            if installation is None or not gff_specialized:
                editor = _instantiate_editor(GFFEditor)
            else:
                editor = _instantiate_editor(specialized_editor_class)
        else:
            # Fallback to simple mapping or None
            if restype in editor_mappings:
                editor_class, requires_installation = editor_mappings[restype]
                editor = _instantiate_editor(editor_class, requires_installation=requires_installation)
            else:
                editor = None

    if restype in {ResourceType.MDL, ResourceType.MDX}:
        editor = _instantiate_editor(MDLEditor)

    elif restype.target_type().contents == "gff" and editor is None:
        editor = _instantiate_editor(GFFEditor)

    elif restype.contents == "plaintext" and editor is None:
        editor = TXTEditor(None)

    if editor is None:
        from toolset.gui.helpers.message_box import show_error_message
        show_error_message(tr("Failed to open file"), trf("The selected file format '{format}' is not yet supported.", format=str(restype)), parent_window_widget)
        return None, None

    try:
        editor.load(filepath, resname, restype, data)
        editor.show()
        editor.activateWindow()
        add_window(editor)

    except Exception as e:
        RobustLogger().exception(
            "Failed to open resource editor for '%s.%s' (filepath=%s, gff_specialized=%s)",
            resname,
            restype,
            filepath,
            gff_specialized,
        )
        data_signature = ""
        if isinstance(data, (bytes, bytearray)):
            head = bytes(data[:16])
            if head:
                data_signature = f"\n\nData signature (first 16 bytes): {head.hex(' ')}"
        from toolset.gui.helpers.message_box import show_error_message
        show_error_message(tr("An unexpected error has occurred"), f"{(e.__class__.__name__, str(e))}{data_signature}", parent_window_widget)
        return None, None
    else:
        return filepath, editor


def open_resource_editor_from_path(
    filepath: os.PathLike | str,
    installation: HTInstallation | None = None,
    parent_window: QWidget | None = None,
    *,
    gff_specialized: bool | None = None,
    open_as_generic_gff: bool = False,
) -> tuple[os.PathLike | str | None, Editor | QMainWindow | None]:
    """Open the resource at the given file path in the appropriate editor.

    Infers resname/restype from the path and reads file data, then delegates to
    open_resource_editor. Used by the file tree context menu and double-click.
    """
    path = Path(filepath) if not isinstance(filepath, Path) else filepath
    if not path.is_file():
        RobustLogger().warning("open_resource_editor_from_path: not a file: %s", path)
        from toolset.gui.helpers.message_box import show_warning_message
        show_warning_message(tr("File not found"), trf("The path is not a file: {path}", path=str(path)), parent_window if isinstance(parent_window, QWidget) else None)
        return None, None
    resource = FileResource.from_path(path)
    return open_resource_editor(
        resource,
        installation=installation,
        parent_window=parent_window,
        gff_specialized=gff_specialized,
        open_as_generic_gff=open_as_generic_gff,
    )
