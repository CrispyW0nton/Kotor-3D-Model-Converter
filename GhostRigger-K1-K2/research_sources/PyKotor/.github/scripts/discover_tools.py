#!/usr/bin/env python3
"""Dynamic tool discovery for GitHub Actions workflows.

Scans Tools/ directory and discovers all valid tools with:
- Tools/<ToolName>/src/<toolname>/__main__.py structure
- pyproject.toml with project metadata

Outputs JSON for GitHub Actions matrix.
"""

from __future__ import annotations

import json
import sys

from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[import-not-found,no-redef]
    except ImportError:
        print("Error: tomllib or tomli required", file=sys.stderr)
        sys.exit(1)


def read_pyproject(tool_path: Path) -> dict[str, Any]:
    """Read pyproject.toml if it exists."""
    pyproject_path = tool_path / "pyproject.toml"
    if not pyproject_path.exists():
        return {}

    try:
        with open(pyproject_path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        print(f"Warning: Failed to read {pyproject_path}: {e}", file=sys.stderr)
        return {}


def find_entrypoint(tool_path: Path, src_dir: Path) -> str | None:
    """Find the tool's entrypoint."""
    # Check for __main__.py files
    for main_file in src_dir.rglob("__main__.py"):
        rel_path = main_file.relative_to(src_dir)
        return str(rel_path)
    return None


def discover_tools(tools_dir: Path) -> list[dict[str, Any]]:
    """Discover all valid tools in Tools/ directory."""
    tools = []

    if not tools_dir.exists():
        print(f"Error: Tools directory not found: {tools_dir}", file=sys.stderr)
        return tools

    for tool_dir in sorted(tools_dir.iterdir()):
        if not tool_dir.is_dir():
            continue

        # Skip hidden directories and tests
        if tool_dir.name.startswith(".") or tool_dir.name.lower() in ("tests", "test"):
            continue

        # Check for src directory
        src_dir = tool_dir / "src"
        if not src_dir.exists():
            print(f"Skipping {tool_dir.name}: no src/ directory", file=sys.stderr)
            continue

        # Read pyproject.toml
        pyproject = read_pyproject(tool_dir)
        tool_config = pyproject.get("tool", {})
        pyinstaller_config = tool_config.get("pyinstaller", {})

        # Find entrypoint
        entrypoint = pyinstaller_config.get("entrypoint") or find_entrypoint(tool_dir, src_dir)
        if not entrypoint:
            print(f"Skipping {tool_dir.name}: no entrypoint found", file=sys.stderr)
            continue

        # Extract metadata
        name = tool_dir.name
        build_name = None
        display_name = name
        requires_qt = False

        if "project" in pyproject:
            project = pyproject["project"]
            if "name" in project:
                name = project["name"]

            # Check dependencies for Qt
            if "dependencies" in project:
                deps_str = " ".join(str(d).lower() for d in project["dependencies"])
                if any(qt in deps_str for qt in ["pyqt", "pyside", "qtpy"]):
                    requires_qt = True

        tool_config = pyproject.get("tool", {})
        pyinstaller_config = tool_config.get("pyinstaller", {})
        build_name = pyinstaller_config.get("name") or None

        tool_deps = tool_config.get("dependencies", {})
        if tool_deps.get("qt-api"):
            requires_qt = True

        tool_info = {
            "directory": tool_dir.name,
            "name": name,
            "build_name": build_name or name,
            "display_name": display_name,
            "entrypoint": entrypoint,
            "requires_qt": requires_qt,
            "path": f"Tools/{tool_dir.name}",
        }

        tools.append(tool_info)
        print(f"Discovered: {tool_dir.name} (entrypoint: {entrypoint})", file=sys.stderr)

    return tools


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Discover tools for CI/CD")
    parser.add_argument("--tools-dir", default="Tools", help="Tools directory path")
    parser.add_argument("--format", choices=["json", "github"], default="github", help="Output format (json or github actions output)")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent.parent
    tools_dir = repo_root / args.tools_dir

    tools = discover_tools(tools_dir)

    if not tools:
        print("Error: No tools discovered", file=sys.stderr)
        sys.exit(1)

    # Output
    if args.format == "json":
        print(json.dumps(tools, indent=2))
    else:  # github
        # GitHub Actions format: single-line JSON
        tools_json = json.dumps(tools)
        print(f"tools_matrix={tools_json}")
        print(f"Discovered {len(tools)} tools", file=sys.stderr)


if __name__ == "__main__":
    main()
