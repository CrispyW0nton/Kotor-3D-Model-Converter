#!/usr/bin/env python3
"""Generic PyInstaller build helper - fully dynamic, reads from pyproject.toml.

Discovers tool configuration from pyproject.toml [tool.pyinstaller] section.
All options can be overridden via CLI arguments.

Example pyproject.toml configuration:

[tool.pyinstaller]
console = false          # or true
windowed = true          # or false
hidden-imports = ["module1", "module2"]
exclude-modules = ["PyQt5", "torch"]
icon = "resources/icons/app.ico"
add-data = ["wiki:wiki", "vendor:vendor"]
upx-exclude = ["_uuid.pyd"]
name = "MyCustomName"  # Override binary name
entrypoint = "myapp/__main__.py"  # Override entrypoint
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys

from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[import-not-found,no-redef]
    except ImportError:
        print("Error: tomllib (Python 3.11+) or tomli package required for reading pyproject.toml")
        print("Install with: pip install tomli")
        sys.exit(1)


def detect_os() -> str:
    system = platform.system()
    if system == "Windows":
        return "Windows"
    if system == "Darwin":
        return "Mac"
    if system == "Linux":
        return "Linux"
    raise SystemExit(f"Unsupported OS: {system}")


def run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, check=True, cwd=cwd, env=env)


def path_separator_for_data(os_name: str) -> str:
    """Return the path separator PyInstaller expects in --add-data."""
    return ";" if os_name == "Windows" else ":"


def add_flag_values(flag_name: str, values: list[str], buffer: list[str]) -> None:
    """Append repeated PyInstaller flag values in --flag=value format."""
    for value in values:
        buffer.append(f"--{flag_name}={value}")


def compute_final_executable(
    distpath: Path,
    name: str,
    os_name: str,
    *,
    windowed: bool = False,
) -> Path:
    """Compute the final binary path from build metadata."""
    if os_name == "Windows":
        return distpath / f"{name}.exe"
    if os_name == "Mac" and windowed:
        return distpath / f"{name}.app"
    return distpath / name


def normalize_add_data(entries: list[str], expected_separator: str) -> list[str]:
    """Validate and normalize --add-data entries for the current platform."""
    normalized: list[str] = []
    for entry in entries:
        if expected_separator not in entry:
            raise SystemExit(
                f"Invalid --add-data entry '{entry}': missing '{expected_separator}' separator"
            )
        source, destination = entry.split(expected_separator, 1)
        if not source or not destination:
            raise SystemExit(
                f"Invalid --add-data entry '{entry}': source and destination are required"
            )
        normalized.append(f"{source}{expected_separator}{destination}")
    return normalized


def read_pyproject_toml(tool_path: Path) -> dict[str, Any]:
    """Read and parse pyproject.toml from tool directory."""
    pyproject_path = tool_path / "pyproject.toml"
    if not pyproject_path.exists():
        return {}

    with open(pyproject_path, "rb") as f:
        return tomllib.load(f)


def discover_tool_metadata(
    tool_path: Path,
    src_dir: Path,
    os_name: str,
    script_name: str | None = None,
) -> dict[str, Any]:
    """Discover tool metadata from filesystem and pyproject.toml."""
    pyproject = read_pyproject_toml(tool_path)

    metadata: dict[str, Any] = {
        "name": None,
        "entrypoint": None,
        "selected_script": None,
        "console": None,
        "windowed": None,
        "icon": None,
        "hidden_imports": [],
        "exclude_modules": [],
        "add_data": [],
        "upx_exclude": [],
        "requires_qt": False,
    }

    # Extract name from pyproject.toml
    if "project" in pyproject and "name" in pyproject["project"]:
        metadata["name"] = pyproject["project"]["name"]

    # Extract entry point from [project.scripts]
    if "project" in pyproject and "scripts" in pyproject["project"]:
        scripts = pyproject["project"]["scripts"]
        if scripts:
            selected_script = script_name or list(scripts.keys())[0]
            if script_name and script_name not in scripts:
                available = ", ".join(sorted(scripts.keys()))
                raise SystemExit(
                    f"Script '{script_name}' not found in [project.scripts]. "
                    f"Available scripts: {available}"
                )
            script_path = scripts[selected_script]
            # Convert 'toolset.__main__:main' to 'toolset/__main__.py'
            if ":" in script_path:
                module_path = script_path.split(":")[0]
                metadata["entrypoint"] = module_path.replace(".", "/") + ".py"
            metadata["selected_script"] = selected_script

    # Fallback: search for __main__.py in src directory
    if not metadata["entrypoint"]:
        for candidate in src_dir.rglob("__main__.py"):
            rel = candidate.relative_to(src_dir)
            metadata["entrypoint"] = str(rel)
            break

    # Check if tool requires Qt by inspecting dependencies
    if "project" in pyproject and "dependencies" in pyproject["project"]:
        deps = pyproject["project"]["dependencies"]
        for dep in deps:
            dep_lower = str(dep).lower()
            if any(qt in dep_lower for qt in ["pyqt", "pyside", "qtpy"]):
                metadata["requires_qt"] = True
                break

    # Read PyInstaller-specific configuration from [tool.pyinstaller]
    if "tool" in pyproject and "pyinstaller" in pyproject["tool"]:
        pi_config = pyproject["tool"]["pyinstaller"]

        if "name" in pi_config:
            metadata["name"] = pi_config["name"]
        if "entrypoint" in pi_config:
            metadata["entrypoint"] = pi_config["entrypoint"]
        if "console" in pi_config:
            metadata["console"] = pi_config["console"]
        if "windowed" in pi_config:
            metadata["windowed"] = pi_config["windowed"]
        if "hidden-imports" in pi_config:
            metadata["hidden_imports"] = pi_config["hidden-imports"]
        if "exclude-modules" in pi_config:
            metadata["exclude_modules"] = pi_config["exclude-modules"]
        if "icon" in pi_config:
            metadata["icon"] = pi_config["icon"]
        if "add-data" in pi_config:
            metadata["add_data"] = pi_config["add-data"]
        if "upx-exclude" in pi_config:
            metadata["upx_exclude"] = pi_config["upx-exclude"]

    return metadata


def find_icon(src_dir: Path, os_name: str) -> str | None:
    """Auto-discover icon file in tool's resource directory."""
    icon_ext = "icns" if os_name == "Mac" else "ico"

    # Search for icons in common locations
    for pattern in [
        f"**/resources/icons/*.{icon_ext}",
        f"**/resources/*.{icon_ext}",
        f"**/*.{icon_ext}",
    ]:
        for icon_path in src_dir.glob(pattern):
            if icon_path.is_file():
                return str(icon_path)

    return None


def build_pyinstaller_args(
    metadata: dict[str, Any],
    args: argparse.Namespace,
    tool_path: Path,
    src_dir: Path,
    repo_root: Path,
    os_name: str,
    python_exe: str,
) -> list[str]:
    """Build PyInstaller command line arguments from metadata and CLI args."""
    cmd = [python_exe, "-m", "PyInstaller"]

    # Console/windowed mode: CLI args override metadata
    if args.windowed:
        cmd.append("--windowed")
    elif args.console:
        cmd.append("--console")
    elif metadata.get("windowed"):
        cmd.append("--windowed")
    elif metadata.get("console") is not None:
        if metadata["console"]:
            cmd.append("--console")
        else:
            cmd.append("--windowed")
    else:
        # Default to console
        cmd.append("--console")

    # One-file mode
    if args.onefile:
        cmd.append("--onefile")

    # Clean and noconfirm
    if args.clean:
        cmd.append("--clean")
    if args.noconfirm:
        cmd.append("--noconfirm")

    # Name: CLI > metadata > tool directory name
    name = args.name or metadata.get("name") or tool_path.name
    cmd.extend(["--name", name])

    # Icon: CLI > metadata > auto-discover
    icon = args.icon or metadata.get("icon")
    if icon:
        icon_path = Path(icon)
        if not icon_path.is_absolute():
            icon_path = tool_path / icon
        if icon_path.exists():
            cmd.extend(["--icon", str(icon_path)])
    else:
        auto_icon = find_icon(src_dir, os_name)
        if auto_icon:
            cmd.extend(["--icon", auto_icon])

    # Hidden imports: merge CLI + metadata
    hidden_imports = list(args.hidden_import) + metadata.get("hidden_imports", [])
    for hidden in hidden_imports:
        cmd.extend(["--hidden-import", hidden])

    # Exclude modules: merge CLI + metadata
    exclude_modules = list(args.exclude_module) + metadata.get("exclude_modules", [])

    # Auto-exclude other Qt backends if --exclude-other-qt or tool uses Qt with specific API
    if args.exclude_other_qt or (metadata.get("requires_qt") and args.qt_api):
        qt_backends = ["PyQt5", "PyQt6", "PySide2", "PySide6"]
        if args.qt_api:
            # Remove the specified Qt API from exclusion list
            qt_backends = [qb for qb in qt_backends if qb != args.qt_api]
        exclude_modules.extend(qt_backends)

    for exclude in set(exclude_modules):  # Deduplicate
        cmd.extend(["--exclude-module", exclude])

    # Add data: merge CLI + metadata
    data_sep = path_separator_for_data(os_name)
    add_data_list = list(args.add_data) + metadata.get("add_data", [])

    # Process add-data entries
    for data_spec in add_data_list:
        # Handle both ":" and ";" separators from metadata
        if ":" in data_spec and os_name != "Windows":
            # Unix-style separator
            cmd.extend(["--add-data", data_spec])
        elif ";" in data_spec and os_name == "Windows":
            # Windows-style separator
            cmd.extend(["--add-data", data_spec])
        else:
            # Need to normalize separator
            if ":" in data_spec:
                src, dst = data_spec.split(":", 1)
            elif ";" in data_spec:
                src, dst = data_spec.split(";", 1)
            else:
                print(f"Warning: invalid add-data spec '{data_spec}', skipping")
                continue

            # Resolve relative paths
            src_path = Path(src)
            if not src_path.is_absolute():
                src_path = tool_path / src_path

            if src_path.exists():
                cmd.extend(["--add-data", f"{src_path}{data_sep}{dst}"])
            else:
                print(f"Warning: add-data source not found: {src_path}, skipping")

    # Auto-add wiki if requested
    if args.include_wiki_if_present:
        wiki_src = repo_root / "wiki"
        if wiki_src.exists():
            cmd.extend(["--add-data", f"{wiki_src}{data_sep}wiki"])

    # UPX
    if args.upx_dir:
        cmd.extend(["--upx-dir", args.upx_dir])

    upx_excludes = list(args.upx_exclude) + metadata.get("upx_exclude", [])
    for upx_ex in upx_excludes:
        cmd.extend(["--upx-exclude", upx_ex])

    # Dist path
    dist_path = args.dist_path or (repo_root / "dist")
    cmd.extend(["--distpath", str(dist_path)])

    # Work path
    work_path = args.work_path or (src_dir / "build")
    cmd.extend(["--workpath", str(work_path)])

    # Paths: always include src + library paths
    cmd.extend(["--path", str(src_dir)])

    # Auto-include Libraries/*/src paths
    libraries_dir = repo_root / "Libraries"
    if libraries_dir.exists():
        for lib_dir in libraries_dir.iterdir():
            lib_src = lib_dir / "src"
            if lib_src.exists():
                cmd.extend(["--path", str(lib_src)])

    # Additional paths from CLI
    for extra_path in args.extra_path:
        cmd.extend(["--path", extra_path])

    # Debug options
    if args.debug:
        cmd.extend(["--debug", args.debug])
    if args.log_level:
        cmd.extend(["--log-level", args.log_level])

    # Entry point (must be last positional argument)
    entrypoint = args.entrypoint or metadata.get("entrypoint")
    if not entrypoint:
        raise SystemExit("No entrypoint found. Specify --entrypoint, define [project.scripts] in pyproject.toml, or ensure a __main__.py exists in your tool's src directory.")

    entrypoint_path = src_dir / entrypoint
    if not entrypoint_path.exists():
        raise SystemExit(f"Entrypoint not found: {entrypoint_path}")

    cmd.append(str(entrypoint_path))

    return cmd


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Generic PyInstaller build tool - dynamically reads configuration from pyproject.toml",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Tool configuration is read from pyproject.toml [tool.pyinstaller] section.
All options can be overridden via command line arguments.

Example pyproject.toml:
    [tool.pyinstaller]
    console = false
    windowed = true
    hidden-imports = ["module1", "module2"]
    exclude-modules = ["PyQt5", "torch"]
    icon = "resources/icons/app.ico"
    add-data = ["wiki:wiki", "vendor:vendor"]
    upx-exclude = ["_uuid.pyd"]
""",
    )

    # Required
    parser.add_argument("--tool-path", required=True, help="Path to tool directory (e.g., Tools/HolocronToolset)")

    # Optional overrides
    default_python = os.environ.get("pythonExePath") or sys.executable
    parser.add_argument("--python-exe", default=default_python, help="Python executable")
    parser.add_argument("--name", help="Override output binary name (from pyproject.toml or directory name)")
    parser.add_argument("--entrypoint", help="Override entry point, relative to src dir (e.g., toolset/__main__.py)")
    parser.add_argument("--script-name", help="Select script key from [project.scripts] for entrypoint discovery")
    parser.add_argument("--icon", help="Override icon path")
    parser.add_argument("--console", action="store_true", help="Force console mode")
    parser.add_argument("--windowed", action="store_true", help="Force windowed mode")
    parser.add_argument("--onefile", action="store_true", default=True, help="Build one-file bundle")
    parser.add_argument("--no-onefile", dest="onefile", action="store_false")
    parser.add_argument("--clean", action="store_true", default=True, help="Clean PyInstaller cache")
    parser.add_argument("--no-clean", dest="clean", action="store_false")
    parser.add_argument("--noconfirm", action="store_true", default=True, help="Replace output without confirmation")
    parser.add_argument("--no-noconfirm", dest="noconfirm", action="store_false")
    parser.add_argument("--dist-path", help="Output directory for built binaries")
    parser.add_argument("--work-path", help="PyInstaller work directory")
    parser.add_argument("--upx-dir", help="Path to UPX directory")
    parser.add_argument("--debug", help="Debug mode (all/imports/bootloader/noarchive)")
    parser.add_argument("--log-level", help="Log level (TRACE/DEBUG/INFO/WARN/ERROR/CRITICAL)")

    # Lists (append to metadata values)
    parser.add_argument("--hidden-import", action="append", default=[], help="Additional hidden imports")
    parser.add_argument("--exclude-module", action="append", default=[], help="Additional modules to exclude")
    parser.add_argument("--add-data", action="append", default=[], help="Additional data files (src:dst or src;dst)")
    parser.add_argument("--upx-exclude", action="append", default=[], help="Files to exclude from UPX compression")
    parser.add_argument("--extra-path", action="append", default=[], help="Additional --path entries")

    # Qt handling
    parser.add_argument("--qt-api", help="Qt API in use (PyQt5/PyQt6/PySide2/PySide6)")
    parser.add_argument("--exclude-other-qt", action="store_true", help="Exclude other Qt backends when qt-api is set")

    # Special flags
    parser.add_argument("--include-wiki-if-present", action="store_true", help="Include wiki folder if it exists")
    parser.add_argument("--remove-previous", action="store_true", default=True, help="Remove previous build artifacts")
    parser.add_argument("--no-remove-previous", dest="remove_previous", action="store_false")

    args = parser.parse_args()

    # Resolve tool path
    tool_path = Path(args.tool_path)
    if not tool_path.is_absolute():
        tool_path = (repo_root / tool_path).resolve()

    if not tool_path.exists():
        raise SystemExit(f"Tool directory not found: {tool_path}")

    # Find src directory
    src_dir = tool_path / "src"
    if not src_dir.exists():
        raise SystemExit(f"Source directory not found: {src_dir}")

    os_name = detect_os()

    # Discover tool metadata from pyproject.toml
    print(f"Building tool from: {tool_path}")
    print("Reading configuration from pyproject.toml...")
    metadata = discover_tool_metadata(tool_path, src_dir, os_name, script_name=args.script_name)
    print(f"  Tool name: {metadata.get('name') or tool_path.name}")
    print(f"  Selected script: {metadata.get('selected_script') or args.script_name or 'first project.scripts entry'}")
    print(f"  Entry point: {metadata.get('entrypoint') or 'auto-detect'}")
    print(f"  Requires Qt: {metadata.get('requires_qt')}")
    print(f"  Console: {metadata.get('console')}")
    print(f"  Windowed: {metadata.get('windowed')}")

    # Build PyInstaller command
    cmd = build_pyinstaller_args(metadata, args, tool_path, src_dir, repo_root, os_name, args.python_exe)

    # Remove previous artifacts if requested
    if args.remove_previous:
        name = args.name or metadata.get("name") or tool_path.name
        dist_path = Path(args.dist_path) if args.dist_path else (repo_root / "dist")

        # Determine expected output based on windowed/console mode
        is_windowed = args.windowed or (not args.console and metadata.get("windowed"))

        if os_name == "Mac" and is_windowed:
            artifact = dist_path / f"{name}.app"
        elif os_name == "Windows":
            artifact = dist_path / f"{name}.exe"
        else:
            artifact = dist_path / name

        if artifact.exists():
            print(f"Removing previous artifact: {artifact}")
            if artifact.is_dir():
                shutil.rmtree(artifact)
            else:
                artifact.unlink()

        # Also remove work directory if cleaning
        if args.clean:
            work_path = Path(args.work_path) if args.work_path else (src_dir / "build")
            if work_path.exists():
                print(f"Removing work directory: {work_path}")
                shutil.rmtree(work_path)

    # Set Qt environment variable if specified
    env = os.environ.copy()
    if args.qt_api:
        env["QT_API"] = args.qt_api

    print("\nRunning PyInstaller...")
    print(f"Command: {' '.join(cmd)}\n")

    try:
        run(cmd, cwd=src_dir, env=env)
        print(f"\n[SUCCESS] Build complete for {tool_path.name}")
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Build failed with exit code {e.returncode}")
        sys.exit(e.returncode)


if __name__ == "__main__":
    main()
