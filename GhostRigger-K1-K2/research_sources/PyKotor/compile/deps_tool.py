#!/usr/bin/env python3
"""Generic dependency installer - fully dynamic, reads from pyproject.toml.

Automatically discovers and installs dependencies from:
- Tool's pyproject.toml [project.dependencies]
- Tool's requirements.txt
- System packages based on detected needs (Qt/Tk)
- [tool.dependencies] section for build-specific needs

All options can be overridden via CLI arguments.
"""

from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys

from pathlib import Path
from typing import Any, Iterable

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[import-not-found,no-redef]
    except ImportError:
        print("Error: tomllib (Python 3.11+) or tomli package required")
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


def detect_linux_distro() -> str | None:
    os_release = Path("/etc/os-release")
    if not os_release.exists():
        return None
    content = os_release.read_text(encoding="utf-8").splitlines()
    for line in content:
        if line.startswith("ID="):
            distro = line.split("=", 1)[1].strip('"').strip("'")
            return "oracle" if distro == "ol" else distro
    return None


def run(cmd: list[str], allow_fail: bool = False) -> None:
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        if allow_fail:
            return
        raise


def read_pyproject_toml(tool_path: Path) -> dict[str, Any]:
    """Read and parse pyproject.toml from tool directory."""
    pyproject_path = tool_path / "pyproject.toml"
    if not pyproject_path.exists():
        return {}

    with open(pyproject_path, "rb") as f:
        return tomllib.load(f)


def analyze_dependencies(tool_path: Path) -> dict[str, Any]:
    """Analyze tool's dependencies and determine what's needed."""
    pyproject = read_pyproject_toml(tool_path)

    analysis = {
        "requires_qt": False,
        "requires_tk": False,
        "requires_playwright": False,
        "qt_api": None,
        "python_packages": [],
        "requirements_files": [],
        "windows_packages": [],
        "linux_profiles": [],
        "brew_packages": [],
    }

    # Check project dependencies
    if "project" in pyproject and "dependencies" in pyproject["project"]:
        deps = pyproject["project"]["dependencies"]
        for dep in deps:
            dep_lower = str(dep).lower()

            # Detect Qt
            if "pyqt5" in dep_lower:
                analysis["requires_qt"] = True
                analysis["qt_api"] = analysis["qt_api"] or "PyQt5"
            elif "pyqt6" in dep_lower:
                analysis["requires_qt"] = True
                analysis["qt_api"] = analysis["qt_api"] or "PyQt6"
            elif "pyside2" in dep_lower:
                analysis["requires_qt"] = True
                analysis["qt_api"] = analysis["qt_api"] or "PySide2"
            elif "pyside6" in dep_lower:
                analysis["requires_qt"] = True
                analysis["qt_api"] = analysis["qt_api"] or "PySide6"

            # Detect Tk
            if "tkinter" in dep_lower or "tk" == dep_lower:
                analysis["requires_tk"] = True

            # Detect Playwright
            if "playwright" in dep_lower:
                analysis["requires_playwright"] = True

    # Read [tool.dependencies] for build-specific configuration
    if "tool" in pyproject and "dependencies" in pyproject["tool"]:
        dep_config = pyproject["tool"]["dependencies"]

        if "linux-profiles" in dep_config:
            analysis["linux_profiles"] = dep_config["linux-profiles"]
        if "brew-packages" in dep_config:
            analysis["brew_packages"] = dep_config["brew-packages"]
        if "windows-packages" in dep_config:
            analysis["windows_packages"] = dep_config["windows-packages"]
        if "qt-api" in dep_config:
            analysis["qt_api"] = dep_config["qt-api"]
        if "playwright-browsers" in dep_config:
            analysis["playwright_browsers"] = dep_config["playwright-browsers"]

    # Auto-detect system package needs if not specified
    if not analysis["linux_profiles"]:
        if analysis["requires_qt"]:
            analysis["linux_profiles"].append("qt_gui")
        elif analysis["requires_tk"]:
            analysis["linux_profiles"].append("tk")

    if not analysis["brew_packages"] and analysis["requires_qt"]:
        analysis["brew_packages"] = ["qt@5", "qt@6"]

    # Find requirements.txt
    requirements_txt = tool_path / "requirements.txt"
    if requirements_txt.exists():
        analysis["requirements_files"].append(str(requirements_txt))

    return analysis


LINUX_PACKAGE_PROFILES: dict[str, dict[str, list[str]]] = {
    "tk": {
        "debian": ["tcl8.6", "tk8.6", "tcl8.6-dev", "tk8.6-dev", "python3-tk", "python3-pip"],
        "ubuntu": ["tcl8.6", "tk8.6", "tcl8.6-dev", "tk8.6-dev", "python3-tk", "python3-pip"],
        "fedora": ["tk-devel", "tcl-devel", "python3-tkinter"],
        "almalinux": ["tk-devel", "tcl-devel", "python3-tkinter"],
        "rocky": ["tk-devel", "tcl-devel", "python3-tkinter"],
        "alpine": ["tcl", "tk", "python3-tkinter", "ttf-dejavu", "fontconfig"],
        "arch": ["tk", "tcl", "mpdecimal"],
        "manjaro": ["tk", "tcl", "mpdecimal"],
        "opensuse": ["tk-devel", "tcl-devel", "python3-tk"],
    },
    "qt_gui": {
        "debian": [
            "libicu-dev",
            "libunwind-dev",
            "libwebp-dev",
            "liblzma-dev",
            "libjpeg-dev",
            "libtiff-dev",
            "libquadmath0",
            "libgfortran5",
            "libopenblas-dev",
            "libxau-dev",
            "libxcb1-dev",
            "python3-opengl",
            "python3-pyqt5",
            "libpulse-mainloop-glib0",
            "libgstreamer-plugins-base1.0-dev",
            "gstreamer1.0-plugins-base",
            "gstreamer1.0-plugins-good",
            "gstreamer1.0-plugins-bad",
            "gstreamer1.0-plugins-ugly",
            "libgstreamer1.0-dev",
            "mesa-utils",
            "libgl1-mesa-glx",
            "libgl1-mesa-dri",
            "qtbase5-dev",
            "qtchooser",
            "qt5-qmake",
            "qtbase5-dev-tools",
            "libglu1-mesa",
            "libglu1-mesa-dev",
            "libqt5gui5",
            "libqt5core5a",
            "libqt5dbus5",
            "libqt5widgets5",
        ],
        "ubuntu": [
            "libicu-dev",
            "libunwind-dev",
            "libwebp-dev",
            "liblzma-dev",
            "libjpeg-dev",
            "libtiff-dev",
            "libquadmath0",
            "libgfortran5",
            "libopenblas-dev",
            "libxau-dev",
            "libxcb1-dev",
            "python3-opengl",
            "python3-pyqt5",
            "libpulse-mainloop-glib0",
            "libgstreamer-plugins-base1.0-dev",
            "gstreamer1.0-plugins-base",
            "gstreamer1.0-plugins-good",
            "gstreamer1.0-plugins-bad",
            "gstreamer1.0-plugins-ugly",
            "libgstreamer1.0-dev",
            "mesa-utils",
            "libgl1-mesa-glx",
            "libgl1-mesa-dri",
            "qtbase5-dev",
            "qtchooser",
            "qt5-qmake",
            "qtbase5-dev-tools",
            "libglu1-mesa",
            "libglu1-mesa-dev",
            "libqt5gui5",
            "libqt5core5a",
            "libqt5dbus5",
            "libqt5widgets5",
        ],
        "fedora": [
            "binutils",
            "libnsl",
            "mesa-libGL-devel",
            "python3-pyopengl",
            "PyQt5",
            "pulseaudio-libs-glib2",
            "gstreamer1-plugins-base",
            "gstreamer1-plugins-good",
            "gstreamer1-plugins-bad-free",
            "gstreamer1-plugins-ugly-free",
            "gstreamer1-devel",
        ],
        "oracle": [
            "binutils",
            "PyQt5",
            "mesa-libGL-devel",
            "pulseaudio-libs-glib2",
            "gstreamer1-plugins-base",
            "gstreamer1-plugins-good",
            "gstreamer1-plugins-bad-free",
            "gstreamer1-plugins-ugly-free",
            "gstreamer1-devel",
        ],
        "almalinux": [
            "binutils",
            "libnsl",
            "libglvnd-opengl",
            "python3-qt5",
            "python3-pyqt5-sip",
            "pulseaudio-libs-glib2",
            "pulseaudio-libs-devel",
            "gstreamer1-plugins-base",
            "gstreamer1-plugins-good",
            "gstreamer1-plugins-bad-free",
            "mesa-libGLw",
            "libX11",
            "mesa-dri-drivers",
            "mesa-libGL",
            "mesa-libglapi",
        ],
        "alpine": [
            "binutils",
            "gstreamer",
            "gstreamer-dev",
            "gst-plugins-bad-dev",
            "gst-plugins-base-dev",
            "pulseaudio-qt",
            "pulseaudio",
            "pulseaudio-alsa",
            "py3-opengl",
            "qt5-qtbase-x11",
            "qt5-qtbase-dev",
            "mesa-gl",
            "mesa-glapi",
            "libx11",
            "ttf-dejavu",
            "fontconfig",
        ],
        "arch": [
            "mesa",
            "libxcb",
            "qt5-base",
            "qt5-wayland",
            "xcb-util-wm",
            "xcb-util-keysyms",
            "xcb-util-image",
            "xcb-util-renderutil",
            "python-opengl",
            "libxcomposite",
            "gtk3",
            "atk",
            "mpdecimal",
            "python-pyqt5",
            "qt5-multimedia",
            "qt5-svg",
            "pulseaudio",
            "pulseaudio-alsa",
            "gstreamer",
            "libglvnd",
            "ttf-dejavu",
            "fontconfig",
            "gst-plugins-base",
            "gst-plugins-good",
            "gst-plugins-bad",
            "gst-plugins-ugly",
        ],
        "manjaro": [
            "mesa",
            "libxcb",
            "qt5-base",
            "qt5-wayland",
            "xcb-util-wm",
            "xcb-util-keysyms",
            "xcb-util-image",
            "xcb-util-renderutil",
            "python-opengl",
            "libxcomposite",
            "gtk3",
            "atk",
            "mpdecimal",
            "python-pyqt5",
            "qt5-multimedia",
            "qt5-svg",
            "pulseaudio",
            "pulseaudio-alsa",
            "gstreamer",
            "libglvnd",
            "ttf-dejavu",
            "fontconfig",
            "gst-plugins-base",
            "gst-plugins-good",
            "gst-plugins-bad",
            "gst-plugins-ugly",
        ],
        "opensuse": ["qt5-qtbase-devel", "libqt5-qtbase", "python3-qt5"],
    },
}


def install_linux_profile(profile: str, distro: str) -> None:
    packages = LINUX_PACKAGE_PROFILES.get(profile, {}).get(distro)
    if not packages:
        print(f"Warning: No package profile '{profile}' for distro '{distro}'")
        return
    print(f"Installing Linux packages for profile '{profile}' on {distro}...")
    if distro in ("debian", "ubuntu"):
        run(["sudo", "apt-get", "update", "-y"], allow_fail=True)
        run(["sudo", "apt-get", "install", "-y", *packages])
    elif distro == "fedora":
        run(["sudo", "dnf", "install", "-y", *packages])
    elif distro in ("almalinux", "oracle", "rocky"):
        run(["sudo", "yum", "install", "-y", *packages])
    elif distro == "alpine":
        run(["sudo", "apk", "add", "--update", *packages])
    elif distro in ("arch", "manjaro"):
        run(["sudo", "pacman", "-Sy", "--needed", "--noconfirm", *packages])
    elif distro == "opensuse":
        run(["sudo", "zypper", "install", "-y", *packages])
    else:
        print(f"Warning: Distro '{distro}' not handled for profile '{profile}'")


def install_brew_packages(packages: Iterable[str]) -> None:
    for package in packages:
        print(f"Installing brew package: {package}")
        run(["brew", "install", package], allow_fail=True)


def venv_python_executable(repo_root: Path, venv_name: str, os_name: str) -> Path:
    if os_name == "Windows":
        return repo_root / venv_name / "Scripts" / "python.exe"
    return repo_root / venv_name / "bin" / "python"


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Generic dependency installer - dynamically reads from pyproject.toml",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Dependencies are automatically discovered from:
  - Tool's pyproject.toml [project.dependencies]
  - Tool's requirements.txt
  - System package needs (auto-detected from dependencies)

Configuration can be added to pyproject.toml [tool.dependencies]:
  [tool.dependencies]
  linux-profiles = ["qt_gui"]
  brew-packages = ["qt@6"]
  windows-packages = ["comtypes", "pywin32"]
  qt-api = "PyQt6"
  playwright-browsers = ["chromium"]
""",
    )

    # Required
    parser.add_argument("--tool-path", required=True, help="Path to tool directory (e.g., Tools/HolocronToolset)")

    # Venv options
    parser.add_argument("--venv-name", default=".venv", help="Virtual environment name")
    parser.add_argument("--skip-venv", action="store_true", help="Skip venv creation (use existing)")
    parser.add_argument("--noprompt", action="store_true", help="Skip prompts in venv creation")
    parser.add_argument("--force-python-version", help="Force Python version for venv")
    parser.add_argument("--python-exe", default=os.environ.get("pythonExePath", "python"), help="Python executable")

    # Pip options
    parser.add_argument("--pip-upgrade", action="store_true", default=True, help="Upgrade pip")
    parser.add_argument("--no-pip-upgrade", dest="pip_upgrade", action="store_false")
    parser.add_argument("--pip-install-pyinstaller", default="pyinstaller", help="PyInstaller package spec")
    parser.add_argument("--no-pip-install-pyinstaller", dest="pip_install_pyinstaller", action="store_const", const="")

    # Override options (append to auto-detected)
    parser.add_argument("--pip-requirements", action="append", default=[], help="Additional requirements files")
    parser.add_argument("--pip-package", action="append", default=[], help="Additional pip packages")
    parser.add_argument("--linux-package-profile", action="append", default=[], help="Additional Linux profiles")
    parser.add_argument("--brew-package", action="append", default=[], help="Additional Homebrew packages")
    parser.add_argument("--windows-extra-pip", action="append", default=[], help="Additional Windows packages")

    # Qt/Playwright
    parser.add_argument("--qt-api", help="Qt binding to install (overrides auto-detect)")
    parser.add_argument("--qt-install-using-brew", action="store_true", help="Install Qt via Homebrew on macOS")
    parser.add_argument("--playwright-browser", action="append", default=[], help="Playwright browsers to install")

    args = parser.parse_args()

    # Resolve tool path
    tool_path = Path(args.tool_path)
    if not tool_path.is_absolute():
        tool_path = (repo_root / tool_path).resolve()

    if not tool_path.exists():
        raise SystemExit(f"Tool directory not found: {tool_path}")

    os_name = detect_os()

    # Analyze tool dependencies
    print(f"Analyzing dependencies for: {tool_path.name}")
    analysis = analyze_dependencies(tool_path)
    print(f"  Requires Qt: {analysis['requires_qt']}")
    print(f"  Requires Tk: {analysis['requires_tk']}")
    print(f"  Requires Playwright: {analysis['requires_playwright']}")
    if analysis["qt_api"]:
        print(f"  Qt API: {analysis['qt_api']}")

    # Determine Python executable
    python_exe = args.python_exe
    if args.skip_venv:
        python_exe_path = Path(python_exe)
        if not python_exe_path.exists():
            raise SystemExit(f"Python executable not found: {python_exe}")
    else:
        # Create venv
        installer = repo_root / "install_python_venv.ps1"
        if not installer.exists():
            raise SystemExit(f"install_python_venv.ps1 not found at {installer}")

        install_cmd = ["pwsh", "-File", str(installer)]
        if args.noprompt:
            install_cmd.append("-noprompt")
        install_cmd.extend(["-venv_name", args.venv_name])
        if args.force_python_version:
            install_cmd.extend(["-force_python_version", args.force_python_version])

        print(f"Creating virtual environment: {args.venv_name}")
        run(install_cmd)

        # Switch to venv Python
        venv_python = venv_python_executable(repo_root, args.venv_name, os_name)
        if venv_python.exists():
            python_exe = str(venv_python)
        else:
            # Fallback to versioned venvs
            for alt_venv in [".venv_3.13", ".venv_3.12", ".venv_3.11", ".venv_3.10", ".venv_3.9", ".venv_3.8"]:
                alt_python = venv_python_executable(repo_root, alt_venv, os_name)
                if alt_python.exists():
                    python_exe = str(alt_python)
                    break
            else:
                raise SystemExit(f"Venv creation failed: expected at {venv_python}")

    # Detect Python implementation
    python_impl = subprocess.check_output(
        [python_exe, "-c", "import platform; print(platform.python_implementation())"],
        text=True,
    ).strip()
    print(f"  Python: {python_impl} at {python_exe}")

    # Upgrade pip
    if args.pip_upgrade:
        print("Upgrading pip...")
        run([python_exe, "-m", "pip", "install", "--upgrade", "pip", "--prefer-binary", "--progress-bar", "on"])

    # Install PyInstaller
    if args.pip_install_pyinstaller:
        print(f"Installing {args.pip_install_pyinstaller}...")
        run([python_exe, "-m", "pip", "install", args.pip_install_pyinstaller, "--prefer-binary", "--progress-bar", "on"])

    # Install from requirements files
    requirements = analysis["requirements_files"] + args.pip_requirements
    for req_file in requirements:
        print(f"Installing from: {req_file}")
        run([python_exe, "-m", "pip", "install", "-r", req_file, "--prefer-binary", "--compile", "--progress-bar", "on"])

    # Install additional pip packages
    if args.pip_package:
        print(f"Installing additional packages: {', '.join(args.pip_package)}")
        run([python_exe, "-m", "pip", "install", *args.pip_package, "--prefer-binary", "--progress-bar", "on"])

    # Install Qt binding
    qt_api = args.qt_api or analysis["qt_api"]
    if qt_api:
        print(f"Installing Qt binding: {qt_api}")
        run([python_exe, "-m", "pip", "install", "-U", qt_api, "--prefer-binary", "--progress-bar", "on"])
        run([python_exe, "-m", "pip", "install", "-U", "qtpy", "--prefer-binary", "--progress-bar", "on"])

    # OS-specific packages
    if os_name == "Mac":
        if args.qt_install_using_brew or (analysis["requires_qt"] and not qt_api):
            print("Installing Qt via Homebrew...")
            install_brew_packages(["qt@5", "qt@6"])

        brew_packages = analysis["brew_packages"] + args.brew_package
        if brew_packages:
            print(f"Installing Homebrew packages: {', '.join(brew_packages)}")
            install_brew_packages(brew_packages)

    elif os_name == "Linux":
        distro = detect_linux_distro()
        if distro:
            profiles = analysis["linux_profiles"] + args.linux_package_profile
            for profile in profiles:
                install_linux_profile(profile, distro)

    elif os_name == "Windows":
        win_packages = analysis["windows_packages"] + args.windows_extra_pip
        # Auto-add Windows-specific packages for CPython
        if python_impl == "CPython":
            if "comtypes" not in win_packages:
                win_packages.append("comtypes")
            if "pywin32" not in win_packages:
                win_packages.append("pywin32")

        if win_packages:
            print(f"Installing Windows packages: {', '.join(win_packages)}")
            run([python_exe, "-m", "pip", "install", *win_packages, "--prefer-binary", "--progress-bar", "on"])

    # Install Playwright browsers
    if analysis["requires_playwright"] or args.playwright_browser:
        browsers = args.playwright_browser or analysis.get("playwright_browsers", ["chromium"])
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "0")
        for browser in browsers:
            print(f"Installing Playwright browser: {browser}")
            run([python_exe, "-m", "playwright", "install", browser])

    print(f"\n[SUCCESS] Dependencies installed for {tool_path.name}")


if __name__ == "__main__":
    main()
