#!/usr/bin/env python3
"""Compile standalone Holocron editors/apps into individual executables."""

from __future__ import annotations

import argparse
import subprocess
import sys

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_registries() -> tuple[list[str], list[str]]:
    repo = _repo_root()
    tool_src = repo / "Tools" / "HolocronToolset" / "src"
    if str(tool_src) not in sys.path:
        sys.path.insert(0, str(tool_src))
    from toolset.gui.editors.standalone import APP_REGISTRY, EDITOR_REGISTRY  # noqa: PLC0415

    return sorted(EDITOR_REGISTRY.keys()), sorted(APP_REGISTRY.keys())


def _script_name_for_editor(editor_name: str) -> str:
    if editor_name == "twoda":
        return "kotor-2da-editor"
    return f"kotor-{editor_name}-editor"


def _script_name_for_app(app_name: str) -> str:
    return f"kotor-{app_name}"


def _run_compile(script_name: str, output_name: str, passthrough: list[str]) -> int:
    repo = _repo_root()
    cmd = [
        sys.executable,
        str(repo / "compile" / "compile_tool.py"),
        "--tool-path",
        "Tools/HolocronToolset",
        "--script-name",
        script_name,
        "--name",
        output_name,
        "--windowed",
        *passthrough,
    ]
    print(f"\n=== Building: {output_name} ({script_name}) ===")
    return subprocess.run(cmd, cwd=repo, check=False).returncode


def main() -> int:
    editors, apps = _load_registries()
    parser = argparse.ArgumentParser(
        description="Compile standalone editors/apps to individual EXEs via compile_tool.py",
    )
    parser.add_argument("--list", action="store_true", help="List supported editor/app keys and exit.")
    parser.add_argument("--all", action="store_true", help="Compile all editors and standalone apps.")
    parser.add_argument("--editor", choices=editors, help="Compile one editor by key.")
    parser.add_argument("--app", choices=apps, help="Compile one standalone app by key.")
    args, passthrough = parser.parse_known_args()

    if args.list:
        print("Editors:")
        for name in editors:
            print(f"  - {name}")
        print("Apps:")
        for name in apps:
            print(f"  - {name}")
        return 0

    targets: list[tuple[str, str]] = []
    if args.all:
        targets.extend([(_script_name_for_editor(name), _script_name_for_editor(name)) for name in editors])
        targets.extend([(_script_name_for_app(name), _script_name_for_app(name)) for name in apps])
    else:
        if args.editor is not None:
            script_name = _script_name_for_editor(args.editor)
            targets.append((script_name, script_name))
        if args.app is not None:
            script_name = _script_name_for_app(args.app)
            targets.append((script_name, script_name))

    if not targets:
        parser.error("Provide --editor NAME, --app NAME, or --all.")

    failures: list[str] = []
    for script_name, output_name in targets:
        code = _run_compile(script_name, output_name, passthrough)
        if code != 0:
            failures.append(script_name)

    if failures:
        print("\nBuilds failed for:")
        for failed in failures:
            print(f"  - {failed}")
        return 1

    print("\nAll requested builds completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

