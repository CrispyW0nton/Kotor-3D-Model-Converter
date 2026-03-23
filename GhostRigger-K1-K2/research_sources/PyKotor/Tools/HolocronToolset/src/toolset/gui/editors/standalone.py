"""Standalone editor launcher for running individual editors without the full toolset.

This module provides the infrastructure to launch any HolocronToolset editor as a
standalone application, independent of the main toolset window.

Usage examples:
    # From command line (after pip install):
    kotor-editor --editor twoda myfile.2da
    kotor-editor --editor gff --game-path "C:/Games/KOTOR" myfile.utc
    kotor-editor --list

    # As a Python module:
    python -m toolset.gui.editors --editor twoda
    python -m toolset.gui.editors.standalone --editor nss myscript.nss

    # Programmatic usage:
    from toolset.gui.editors.standalone import launch_editor
    launch_editor("twoda", file_path="myfile.2da")
"""
from __future__ import annotations

import argparse
import os
import sys

from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from qtpy.QtWidgets import QApplication, QWidget

    from toolset.data.installation import HTInstallation
    from toolset.gui.editor import Editor


# ---------------------------------------------------------------------------
# Editor Registry
# ---------------------------------------------------------------------------

# Maps editor short names / aliases to (module_path, class_name, description)
# The module_path is relative to toolset.gui.editors
EDITOR_REGISTRY: dict[str, tuple[str, str, str, list[str]]] = {
    # name: (module_path, class_name, description, file_extensions)
    "are": ("toolset.gui.editors.are", "AREEditor", "Area Editor", [".are"]),
    "bwm": ("toolset.gui.editors.bwm", "BWMEditor", "Walkmesh Editor", [".wok", ".dwk", ".pwk", ".bwm"]),
    "dlg": ("toolset.gui.editors.dlg", "DLGEditor", "Dialog Editor", [".dlg"]),
    "erf": ("toolset.gui.editors.erf", "ERFEditor", "ERF/MOD/RIM/SAV Editor", [".erf", ".mod", ".rim", ".sav"]),
    "fac": ("toolset.gui.editors.fac", "FACEditor", "Faction Editor", [".fac"]),
    "gff": ("toolset.gui.editors.gff", "GFFEditor", "GFF Editor (Generic)", [".gff"]),
    "git": ("toolset.gui.editors.git", "GITEditor", "GIT Editor", [".git"]),
    "ifo": ("toolset.gui.editors.ifo", "IFOEditor", "Module Info Editor", [".ifo"]),
    "jrl": ("toolset.gui.editors.jrl", "JRLEditor", "Journal Editor", [".jrl"]),
    "lip": ("toolset.gui.editors.lip", "LIPEditor", "LIP Sync Editor", [".lip"]),
    "ltr": ("toolset.gui.editors.ltr", "LTREditor", "Letter Combo Probability Editor", [".ltr"]),
    "mdl": ("toolset.gui.editors.mdl", "MDLEditor", "Model Editor", [".mdl", ".mdx"]),
    "nss": ("toolset.gui.editors.nss", "NSSEditor", "Script Editor", [".nss", ".ncs"]),
    "pth": ("toolset.gui.editors.pth", "PTHEditor", "Path Editor", [".pth"]),
    "savegame": ("toolset.gui.editors.savegame", "SaveGameEditor", "Save Game Editor", []),
    "ssf": ("toolset.gui.editors.ssf", "SSFEditor", "Sound Set Editor", [".ssf"]),
    "tlk": ("toolset.gui.editors.tlk", "TLKEditor", "Talk Table Editor", [".tlk"]),
    "tpc": ("toolset.gui.editors.tpc", "TPCEditor", "Texture Editor", [".tpc", ".tga", ".png", ".jpg", ".bmp", ".dds"]),
    "txt": ("toolset.gui.editors.txt", "TXTEditor", "Text Editor", [".txt", ".ini", ".cfg", ".2da_bak"]),
    "twoda": ("toolset.gui.editors.twoda", "TwoDAEditor", "2DA Table Editor", [".2da"]),
    "utc": ("toolset.gui.editors.utc", "UTCEditor", "Creature Editor", [".utc", ".btc", ".bic"]),
    "utd": ("toolset.gui.editors.utd", "UTDEditor", "Door Editor", [".utd", ".btd"]),
    "ute": ("toolset.gui.editors.ute", "UTEEditor", "Encounter Editor", [".ute", ".bte"]),
    "uti": ("toolset.gui.editors.uti", "UTIEditor", "Item Editor", [".uti", ".bti"]),
    "utm": ("toolset.gui.editors.utm", "UTMEditor", "Store Editor", [".utm", ".btm"]),
    "utp": ("toolset.gui.editors.utp", "UTPEditor", "Placeable Editor", [".utp", ".btp"]),
    "uts": ("toolset.gui.editors.uts", "UTSEditor", "Sound Editor", [".uts"]),
    "utt": ("toolset.gui.editors.utt", "UTTEditor", "Trigger Editor", [".utt", ".btt"]),
    "utw": ("toolset.gui.editors.utw", "UTWEditor", "Waypoint Editor", [".utw"]),
    "wav": ("toolset.gui.editors.wav", "WAVEditor", "Audio Player", [".wav", ".mp3", ".ogg", ".wma"]),
}

# Standalone non-editor apps that should support direct launch and script entry points.
APP_REGISTRY: dict[str, tuple[str, str, str, bool]] = {
    # name: (module_path, class_name, description, requires_installation)
    "module-designer": ("toolset.gui.windows.module_designer", "ModuleDesigner", "Module Designer", True),
    "indoor-builder": ("toolset.gui.windows.indoor_builder.builder", "IndoorMapBuilder", "Indoor Builder", False),
}

# Editors that require a game installation to function.
# These editors call installation methods during __init__ and will fail without one.
# When launching these standalone, the user must provide --game-path or select an installation.
EDITORS_REQUIRING_INSTALLATION: frozenset[str] = frozenset({
    "are",   # Needs installation for script resnames, camera 2DAs
    "git",   # OpenGL renderer + installation-dependent setup
    "utc",   # 2DA batch cache for appearances, classes, etc.
    "utd",   # 2DA lookups for door types
    "ute",   # get_relevant_resources for scripts
    "uti",   # 2DA batch cache for item properties
    "utp",   # 2DA cache for placeable types
})

# Build a reverse mapping from file extension to editor name
_EXTENSION_TO_EDITOR: dict[str, str] = {}
for _editor_name, (_mod, _cls, _desc, _exts) in EDITOR_REGISTRY.items():
    for _ext in _exts:
        _ext_lower = _ext.lower()
        # Don't overwrite if already set (first editor wins for shared extensions)
        if _ext_lower not in _EXTENSION_TO_EDITOR:
            _EXTENSION_TO_EDITOR[_ext_lower] = _editor_name


def get_editor_for_extension(ext: str) -> str | None:
    """Return the editor name for a given file extension, or None if unknown.

    Args:
        ext: File extension including the dot (e.g., ".2da", ".utc")
    """
    return _EXTENSION_TO_EDITOR.get(ext.lower())


def list_editors() -> list[tuple[str, str, list[str]]]:
    """Return a list of (name, description, extensions) for all registered editors."""
    return [(name, info[2], info[3]) for name, info in sorted(EDITOR_REGISTRY.items())]


# ---------------------------------------------------------------------------
# Path Setup (mirrors toolset/__main__.py and toolset/main_init.py)
# ---------------------------------------------------------------------------

def _setup_paths():
    """Set up sys.path for local development (non-installed) usage.

    This mirrors the path setup from toolset/__main__.py to ensure all
    local library packages are importable when running editors standalone.
    """
    file_path = Path(__file__).resolve()
    # standalone.py is at Tools/HolocronToolset/src/toolset/gui/editors/standalone.py
    # repo_root is 6 parents up
    repo_root = file_path.parents[6]

    paths_to_add = [
        file_path.parents[3],  # Tools/HolocronToolset/src/
        repo_root / "Tools" / "KotorDiff" / "src",
        repo_root / "Libraries" / "PyKotor" / "src",
    ]

    for path in paths_to_add:
        path_str = str(path)
        if path.exists() and path_str not in sys.path:
            sys.path.insert(0, path_str)


def _setup_qt_env():
    """Set up Qt environment variables for standalone usage."""
    from toolset.main_init import fix_qt_env_var, is_frozen  # noqa: PLC0415

    if not is_frozen():
        fix_qt_env_var()

    # Ensure real platform plugin (not offscreen)
    os.environ["QT_QPA_PLATFORM"] = ""

    # Platform-specific multimedia settings
    if os.name == "nt":
        os.environ.setdefault("QT_MULTIMEDIA_PREFERRED_PLUGINS", "windowsmediafoundation")
        os.environ.setdefault("QT_MEDIA_BACKEND", "windows")


# ---------------------------------------------------------------------------
# QApplication Setup
# ---------------------------------------------------------------------------

def create_standalone_app(argv: list[str] | None = None) -> QApplication:
    """Create and configure a QApplication for standalone editor use.

    This handles all the initialization that the full toolset does:
    - Qt resource registration (icons, stylesheets)
    - Exception handling hooks
    - Application metadata

    Args:
        argv: Command-line arguments. Defaults to sys.argv.

    Returns:
        Configured QApplication instance.
    """
    from qtpy.QtWidgets import QApplication  # noqa: PLC0415

    # Check if QApplication already exists
    existing_app = QApplication.instance()
    if existing_app is not None:
        return existing_app  # type: ignore[return-value]

    if argv is None:
        argv = sys.argv

    app = QApplication(argv)
    from toolset.gui.common.tooltip_utils import install_tooltip_label_filter

    install_tooltip_label_filter(app)
    app.setApplicationName("HolocronToolset-Editor")
    app.setOrganizationName("PyKotor")
    app.setOrganizationDomain("github.com/OldRepublicDevs/PyKotor")
    app.setApplicationDisplayName("KotOR Editor")

    # Set up exception handling
    from toolset.main_init import on_app_crash  # noqa: PLC0415
    sys.excepthook = on_app_crash

    # Apply post-init settings (fonts, themes, etc.)
    with suppress(Exception):
        from toolset.main_settings import setup_post_init_settings  # noqa: PLC0415
        setup_post_init_settings()

    return app


# ---------------------------------------------------------------------------
# Installation Setup
# ---------------------------------------------------------------------------

def create_installation_from_path(
    game_path: str | os.PathLike,
    name: str = "Standalone",
    *,
    tsl: bool | None = None,
) -> HTInstallation:
    """Create an HTInstallation from a game directory path.

    Args:
        game_path: Path to the KotOR or TSL installation directory.
        name: Display name for this installation.
        tsl: Whether this is a TSL installation. If None, auto-detects.

    Returns:
        Configured HTInstallation instance.
    """
    from toolset.data.installation import HTInstallation  # noqa: PLC0415
    return HTInstallation(game_path, name, tsl=tsl)


def get_saved_installations() -> dict[str, dict[str, Any]]:
    """Retrieve saved installations from toolset settings.

    Returns:
        Dict mapping installation name to config dict with 'path' and 'tsl' keys.
    """
    try:
        from toolset.gui.widgets.settings.installations import GlobalSettings  # noqa: PLC0415
        settings = GlobalSettings()
        installations = settings.installations()
        return {
            name: {"path": config.path, "tsl": config.tsl, "name": name}
            for name, config in installations.items()
        }
    except Exception:  # noqa: BLE001
        return {}


def pick_installation_interactive() -> HTInstallation | None:
    """Show a dialog for the user to pick or configure a game installation.

    Returns:
        HTInstallation if user selected one, None if cancelled.
    """
    from qtpy.QtWidgets import (  # noqa: PLC0415
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QVBoxLayout,
    )

    saved = get_saved_installations()

    dialog = QDialog()
    dialog.setWindowTitle("Select KotOR Installation")
    dialog.setMinimumWidth(500)

    layout = QVBoxLayout(dialog)

    # Header
    header = QLabel(
        "Select a KotOR game installation to enable full editor functionality.\n"
        "Without an installation, editors will have limited features\n"
        "(no talk table, 2DA lookups, or game resource access)."
    )
    header.setWordWrap(True)
    layout.addWidget(header)

    # Saved installations combo
    if saved:
        form = QFormLayout()
        combo = QComboBox()
        combo.addItem("(None - Limited functionality)", None)
        for name, config in saved.items():
            combo.addItem(f"{name} ({config['path']})", config)
        form.addRow("Saved Installation:", combo)
        layout.addLayout(form)
    else:
        combo = None
        layout.addWidget(QLabel("No saved installations found."))

    # Custom path section
    layout.addWidget(QLabel("\n--- Or specify a custom path ---"))
    path_layout = QHBoxLayout()
    path_edit = QLineEdit()
    path_edit.setPlaceholderText("Path to KotOR or TSL game directory...")
    browse_btn = QPushButton("Browse...")
    path_layout.addWidget(path_edit)
    path_layout.addWidget(browse_btn)
    layout.addLayout(path_layout)

    def browse():
        dir_path = QFileDialog.getExistingDirectory(dialog, "Select KotOR/TSL Game Directory")
        if dir_path:
            path_edit.setText(dir_path)
    browse_btn.clicked.connect(browse)

    # Buttons
    button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

    # Add "Skip" button for running without installation
    skip_btn = button_box.addButton("Skip (No Installation)", QDialogButtonBox.ButtonRole.ActionRole)

    skip_result = [False]
    def on_skip():
        skip_result[0] = True
        dialog.accept()
    skip_btn.clicked.connect(on_skip)

    button_box.accepted.connect(dialog.accept)
    button_box.rejected.connect(dialog.reject)
    layout.addWidget(button_box)

    if dialog.exec() == QDialog.DialogCode.Rejected:
        return None

    if skip_result[0]:
        return None

    # Check custom path first
    custom_path = path_edit.text().strip()
    if custom_path and Path(custom_path).is_dir():
        try:
            return create_installation_from_path(custom_path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(dialog, "Invalid Path", f"Could not load installation from path:\n{e}")
            return None

    # Check combo selection
    if combo is not None:
        selected = combo.currentData()
        if selected is not None:
            try:
                return create_installation_from_path(
                    selected["path"],
                    name=selected["name"],
                    tsl=selected.get("tsl"),
                )
            except Exception as e:  # noqa: BLE001
                QMessageBox.warning(dialog, "Invalid Installation", f"Could not load installation:\n{e}")
                return None

    return None


# ---------------------------------------------------------------------------
# Editor Instantiation
# ---------------------------------------------------------------------------

def _import_editor_class(editor_name: str) -> type[Editor]:
    """Dynamically import and return the editor class for the given editor name.

    Args:
        editor_name: Short name from EDITOR_REGISTRY (e.g., "twoda", "gff").

    Returns:
        The editor class.

    Raises:
        KeyError: If editor_name is not in the registry.
        ImportError: If the editor module cannot be imported.
    """
    import importlib  # noqa: PLC0415

    if editor_name not in EDITOR_REGISTRY:
        raise KeyError(
            f"Unknown editor: '{editor_name}'. "
            f"Available editors: {', '.join(sorted(EDITOR_REGISTRY.keys()))}"
        )

    module_path, class_name, _, _ = EDITOR_REGISTRY[editor_name]
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def create_editor(
    editor_name: str,
    parent: QWidget | None = None,
    installation: HTInstallation | None = None,
) -> Editor:
    """Create an editor instance by name.

    Args:
        editor_name: Short name from EDITOR_REGISTRY (e.g., "twoda", "gff").
        parent: Optional parent widget.
        installation: Optional game installation for full functionality.

    Returns:
        An editor instance ready to show.
    """
    editor_class = _import_editor_class(editor_name)
    editor = editor_class(parent, installation)
    if hasattr(editor, "enable_standalone_mode"):
        editor.enable_standalone_mode()
    return editor


def create_app(
    app_name: str,
    parent: QWidget | None = None,
    installation: HTInstallation | None = None,
    file_path: str | os.PathLike | None = None,
) -> QWidget:
    """Create a standalone non-editor app by key from APP_REGISTRY."""
    import importlib  # noqa: PLC0415

    if app_name not in APP_REGISTRY:
        raise KeyError(
            f"Unknown app: '{app_name}'. "
            f"Available apps: {', '.join(sorted(APP_REGISTRY.keys()))}"
        )

    module_path, class_name, _, _ = APP_REGISTRY[app_name]
    module = importlib.import_module(module_path)
    app_class = getattr(module, class_name)

    if app_name == "module-designer":
        if installation is None:
            raise ValueError("Module Designer requires an installation.")
        mod_filepath = Path(file_path).resolve() if file_path is not None else None
        window = app_class(parent, installation, mod_filepath)
        if hasattr(window, "enable_standalone_mode"):
            window.enable_standalone_mode()
        return window

    if app_name == "indoor-builder":
        window = app_class(parent, installation)
        if hasattr(window, "enable_standalone_mode"):
            window.enable_standalone_mode()
        return window

    raise ValueError(f"Unsupported app key: {app_name}")


def detect_editor_for_file(filepath: str | os.PathLike) -> str | None:
    """Detect which editor to use based on a file's extension.

    Args:
        filepath: Path to the file.

    Returns:
        Editor name, or None if the file type is not recognized.
    """
    from pykotor.resource.type import ResourceType  # noqa: PLC0415

    path = Path(filepath)
    ext = path.suffix.lower()

    # Direct extension lookup
    editor_name = get_editor_for_extension(ext)
    if editor_name is not None:
        return editor_name

    # Try PyKotor ResourceType detection for more exotic extensions
    try:
        restype = ResourceType.from_extension(ext)
        if restype.is_invalid:
            return None
        if restype.contents == "plaintext":
            return "txt"
        if restype.contents == "gff":
            return "gff"
        if restype.category in ("Images", "Textures"):
            return "tpc"
        if restype.category == "Audio":
            return "wav"
        if restype.category == "Walkmeshes":
            return "bwm"
    except Exception:  # noqa: BLE001
        pass

    return None


# ---------------------------------------------------------------------------
# Main Launch Function
# ---------------------------------------------------------------------------

def launch_editor(
    editor_name: str | None = None,
    file_path: str | os.PathLike | None = None,
    game_path: str | os.PathLike | None = None,
    *,
    tsl: bool | None = None,
    installation: HTInstallation | None = None,
    ask_installation: bool = True,
    argv: list[str] | None = None,
) -> int:
    """Launch a standalone editor.

    This is the main programmatic entry point for standalone editor usage.

    Args:
        editor_name: Editor name from EDITOR_REGISTRY. If None and file_path is given,
                     auto-detects from file extension.
        file_path: Optional file to open on startup.
        game_path: Optional path to KotOR/TSL installation.
        tsl: Whether the game installation is TSL. Auto-detected if None.
        installation: Pre-configured HTInstallation. Overrides game_path.
        ask_installation: If True and no installation provided, shows a picker dialog.
        argv: Command-line arguments for QApplication.

    Returns:
        Application exit code.
    """
    # Auto-detect editor from file
    if editor_name is None and file_path is not None:
        editor_name = detect_editor_for_file(file_path)
        if editor_name is None:
            print(f"Error: Cannot determine editor for file: {file_path}", file=sys.stderr)
            print("Use --editor to specify the editor explicitly.", file=sys.stderr)
            return 1

    if editor_name is None:
        print("Error: No editor specified and no file provided.", file=sys.stderr)
        print("Use --editor NAME or provide a file path.", file=sys.stderr)
        print("Use --list to see available editors.", file=sys.stderr)
        return 1

    # Create QApplication
    app = create_standalone_app(argv)

    # Set up installation
    if installation is None and game_path is not None:
        try:
            installation = create_installation_from_path(game_path, tsl=tsl)
        except Exception as e:  # noqa: BLE001
            print(f"Warning: Could not load game installation from '{game_path}': {e}", file=sys.stderr)
            print("Continuing without installation (limited functionality).", file=sys.stderr)

    if installation is None and ask_installation:
        # If this editor requires installation, be more insistent about it
        if editor_name in EDITORS_REQUIRING_INSTALLATION:
            print(
                f"Note: The {EDITOR_REGISTRY[editor_name][2]} requires a game installation for full functionality.",
                file=sys.stderr,
            )
        installation = pick_installation_interactive()

    if installation is None and editor_name in EDITORS_REQUIRING_INSTALLATION:
        print(
            f"Warning: The {EDITOR_REGISTRY[editor_name][2]} requires a game installation. "
            "It may fail or have severely limited functionality without one.\n"
            "Use --game-path to specify a KotOR/TSL installation directory.",
            file=sys.stderr,
        )

    # Create and show editor
    try:
        editor = create_editor(editor_name, installation=installation)
    except (KeyError, ImportError, AssertionError, AttributeError) as e:
        import traceback
        traceback.print_exc()
        print(f"Error creating editor: {e.__class__.__name__}: {e}", file=sys.stderr)
        if installation is None and editor_name in EDITORS_REQUIRING_INSTALLATION:
            print(
                "This editor requires a game installation. "
                "Please provide --game-path or select an installation.",
                file=sys.stderr,
            )
        return 1

    # Load file if provided
    if file_path is not None:
        _load_file_into_editor(editor, file_path)

    editor.show()
    editor.activateWindow()

    # Keep reference to prevent garbage collection
    from toolset.utils.window import add_window  # noqa: PLC0415
    add_window(editor, show=False)  # Already shown above

    return app.exec()


def launch_app(
    app_name: str,
    file_path: str | os.PathLike | None = None,
    game_path: str | os.PathLike | None = None,
    *,
    tsl: bool | None = None,
    installation: HTInstallation | None = None,
    ask_installation: bool = True,
    argv: list[str] | None = None,
) -> int:
    """Launch a standalone non-editor app from APP_REGISTRY."""
    if app_name not in APP_REGISTRY:
        print(
            f"Error: Unknown app '{app_name}'. Available apps: {', '.join(sorted(APP_REGISTRY.keys()))}",
            file=sys.stderr,
        )
        return 1

    app = create_standalone_app(argv)

    if installation is None and game_path is not None:
        try:
            installation = create_installation_from_path(game_path, tsl=tsl)
        except Exception as e:  # noqa: BLE001
            print(f"Warning: Could not load game installation from '{game_path}': {e}", file=sys.stderr)
            print("Continuing without installation (limited functionality).", file=sys.stderr)

    app_display_name = APP_REGISTRY[app_name][2]
    requires_installation = APP_REGISTRY[app_name][3]

    if installation is None and ask_installation:
        if requires_installation:
            print(
                f"Note: {app_display_name} requires a game installation for full functionality.",
                file=sys.stderr,
            )
        installation = pick_installation_interactive()

    if installation is None and requires_installation:
        print(
            f"Error: {app_display_name} requires a game installation.\n"
            "Use --game-path to specify a KotOR/TSL installation directory.",
            file=sys.stderr,
        )
        return 1

    try:
        window = create_app(
            app_name,
            installation=installation,
            file_path=file_path,
        )
    except (KeyError, ImportError, AssertionError, AttributeError, ValueError) as e:
        print(f"Error creating app window: {e}", file=sys.stderr)
        return 1

    window.show()
    window.activateWindow()

    from toolset.utils.window import add_window  # noqa: PLC0415
    add_window(window, show=False)

    return app.exec()


def _load_file_into_editor(editor: Editor, file_path: str | os.PathLike):
    """Load a file into an editor instance.

    Args:
        editor: The editor to load the file into.
        file_path: Path to the file to load.
    """
    from pykotor.extract.file import ResourceIdentifier  # noqa: PLC0415

    path = Path(file_path).resolve()
    if not path.is_file():
        print(f"Warning: File not found: {path}", file=sys.stderr)
        return

    try:
        data = path.read_bytes()
        res_ident = ResourceIdentifier.from_path(path).validate()
        editor.load(path, res_ident.resname, res_ident.restype, data)
    except Exception as e:  # noqa: BLE001
        print(f"Warning: Could not load file '{path}': {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the standalone editor CLI."""
    parser = argparse.ArgumentParser(
        prog="kotor-editor",
        description="Launch individual KotOR resource editors as standalone applications.",
        epilog=(
            "Examples:\n"
            "  kotor-editor --editor twoda myfile.2da\n"
            "  kotor-editor myfile.utc --game-path \"C:/Games/KOTOR\"\n"
            "  kotor-editor --editor nss --no-installation\n"
            "  kotor-editor --list\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="File to open. Editor is auto-detected from extension if --editor is not given.",
    )
    parser.add_argument(
        "--editor", "-e",
        choices=sorted(EDITOR_REGISTRY.keys()),
        default=None,
        help="Editor to launch (e.g., twoda, gff, utc, nss).",
    )
    parser.add_argument(
        "--game-path", "-g",
        default=None,
        help="Path to KotOR or TSL game installation directory.",
    )
    parser.add_argument(
        "--tsl",
        action="store_true",
        default=None,
        help="Specify that the game installation is TSL (The Sith Lords).",
    )
    parser.add_argument(
        "--no-installation", "-n",
        action="store_true",
        default=False,
        help="Skip installation picker dialog. Run with limited functionality.",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        default=False,
        help="List all available editors and exit.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the standalone editor launcher.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code.
    """
    # Set up paths before any toolset imports
    _setup_paths()
    _setup_qt_env()

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        print("\nAvailable KotOR Editors:")
        print("-" * 78)
        for name, desc, exts in list_editors():
            ext_str = ", ".join(exts) if exts else "(various)"
            req_marker = " *" if name in EDITORS_REQUIRING_INSTALLATION else ""
            print(f"  {name:<12} {desc:<35} {ext_str}{req_marker}")
        print("-" * 78)
        print("  * = Requires a game installation (--game-path)")
        print("\nUsage: kotor-editor --editor NAME [file]")
        print("       kotor-editor file.ext  (auto-detects editor)")
        return 0

    return launch_editor(
        editor_name=args.editor,
        file_path=args.file,
        game_path=args.game_path,
        tsl=args.tsl if args.tsl else None,
        ask_installation=not args.no_installation,
        argv=sys.argv[:1],  # Pass just the program name to QApplication
    )


def launch_editor_cli(editor_name: str, argv: list[str] | None = None) -> int:
    """Shared CLI helper for direct execution of specific editor modules."""
    _setup_paths()
    _setup_qt_env()

    parser = argparse.ArgumentParser(
        prog=f"kotor-{editor_name}-editor",
        description=EDITOR_REGISTRY[editor_name][2],
    )
    parser.add_argument("file", nargs="?", default=None, help="File to open.")
    parser.add_argument("--game-path", "-g", default=None, help="Path to KotOR/TSL game directory.")
    parser.add_argument("--tsl", action="store_true", default=None, help="TSL installation.")
    parser.add_argument("--no-installation", "-n", action="store_true", default=False, help="Skip installation picker.")
    args = parser.parse_args(argv)

    return launch_editor(
        editor_name=editor_name,
        file_path=args.file,
        game_path=args.game_path,
        tsl=args.tsl if args.tsl else None,
        ask_installation=not args.no_installation,
        argv=sys.argv[:1],
    )


def launch_app_cli(app_name: str, argv: list[str] | None = None) -> int:
    """Shared CLI helper for direct execution of specific app modules."""
    _setup_paths()
    _setup_qt_env()

    app_description = APP_REGISTRY[app_name][2]
    parser = argparse.ArgumentParser(
        prog=f"kotor-{app_name}",
        description=app_description,
    )
    parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="Optional startup file (module path for module designer).",
    )
    parser.add_argument("--game-path", "-g", default=None, help="Path to KotOR/TSL game directory.")
    parser.add_argument("--tsl", action="store_true", default=None, help="TSL installation.")
    parser.add_argument("--no-installation", "-n", action="store_true", default=False, help="Skip installation picker.")
    args = parser.parse_args(argv)

    return launch_app(
        app_name=app_name,
        file_path=args.file,
        game_path=args.game_path,
        tsl=args.tsl if args.tsl else None,
        ask_installation=not args.no_installation,
        argv=sys.argv[:1],
    )


# ---------------------------------------------------------------------------
# Convenience launcher functions (for pyproject.toml entry points)
# ---------------------------------------------------------------------------

def _make_editor_launcher(editor_name: str) -> Callable[[], int]:
    """Create a launcher function for a specific editor.

    Used to generate entry point functions for pyproject.toml console_scripts.
    """
    def launcher() -> int:
        return launch_editor_cli(editor_name)

    launcher.__name__ = f"launch_{editor_name}"
    launcher.__doc__ = f"Launch the {EDITOR_REGISTRY[editor_name][2]} standalone."
    return launcher


# Generate individual launcher functions
launch_are = _make_editor_launcher("are")
launch_bwm = _make_editor_launcher("bwm")
launch_dlg = _make_editor_launcher("dlg")
launch_erf = _make_editor_launcher("erf")
launch_fac = _make_editor_launcher("fac")
launch_gff = _make_editor_launcher("gff")
launch_git = _make_editor_launcher("git")
launch_ifo = _make_editor_launcher("ifo")
launch_jrl = _make_editor_launcher("jrl")
launch_lip = _make_editor_launcher("lip")
launch_ltr = _make_editor_launcher("ltr")
launch_mdl = _make_editor_launcher("mdl")
launch_nss = _make_editor_launcher("nss")
launch_pth = _make_editor_launcher("pth")
launch_savegame = _make_editor_launcher("savegame")
launch_ssf = _make_editor_launcher("ssf")
launch_tlk = _make_editor_launcher("tlk")
launch_tpc = _make_editor_launcher("tpc")
launch_txt = _make_editor_launcher("txt")
launch_twoda = _make_editor_launcher("twoda")
launch_utc = _make_editor_launcher("utc")
launch_utd = _make_editor_launcher("utd")
launch_ute = _make_editor_launcher("ute")
launch_uti = _make_editor_launcher("uti")
launch_utm = _make_editor_launcher("utm")
launch_utp = _make_editor_launcher("utp")
launch_uts = _make_editor_launcher("uts")
launch_utt = _make_editor_launcher("utt")
launch_utw = _make_editor_launcher("utw")
launch_wav = _make_editor_launcher("wav")


def _make_app_launcher(app_name: str) -> Callable[[], int]:
    """Create a launcher function for a specific standalone app."""
    def launcher() -> int:
        return launch_app_cli(app_name)

    launcher.__name__ = f"launch_{app_name.replace('-', '_')}"
    launcher.__doc__ = f"Launch the {APP_REGISTRY[app_name][2]} standalone."
    return launcher


launch_module_designer = _make_app_launcher("module-designer")
launch_indoor_builder = _make_app_launcher("indoor-builder")


if __name__ == "__main__":
    sys.exit(main())
