"""Local Autodesk FBX SDK path configuration helpers."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import importlib
import importlib.util
import json
import platform
from pathlib import Path
import site
import struct
import sys
import traceback
from typing import Any, Iterator

FBX_DOWNLOAD_URL = "https://aps.autodesk.com/developer/overview/fbx-sdk"

DEFAULT_FBX_SDK_SETTINGS: dict[str, Any] = {
    "enabled": False,
    "sdk_root": "",
    "python_bindings_path": "",
    "fbxcommon_path": "",
    "extra_paths": [],
    "last_verified_python": "",
    "last_verified_platform": "",
    "last_verified_ok": False,
}


@dataclass
class FbxSdkTestResult:
    success: bool = False
    fbx_import_ok: bool = False
    fbxcommon_import_ok: bool = False
    manager_create_ok: bool = False
    scene_create_ok: bool = False
    detected_sdk_version: str = ""
    error_message: str = ""
    traceback_text: str = ""
    recommended_fix: str = ""
    tested_paths: list[str] | None = None


def normalize_fbx_sdk_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    data = {**DEFAULT_FBX_SDK_SETTINGS, **dict(settings or {})}
    data["extra_paths"] = [str(item) for item in data.get("extra_paths") or [] if str(item).strip()]
    data["enabled"] = bool(data.get("enabled"))
    data["last_verified_ok"] = bool(data.get("last_verified_ok"))
    return data


def configured_sdk_paths(settings: dict[str, Any] | None) -> list[str]:
    data = normalize_fbx_sdk_settings(settings)
    candidates = [
        data.get("python_bindings_path", ""),
        data.get("fbxcommon_path", ""),
        data.get("sdk_root", ""),
        *data.get("extra_paths", []),
    ]
    paths: list[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(str(candidate)).expanduser()
        if path.is_file():
            path = path.parent
        if path.exists():
            resolved = str(path.resolve())
            if resolved not in paths:
                paths.append(resolved)
    return paths


def apply_configured_sdk_paths(settings: dict[str, Any] | None) -> list[str]:
    """Add configured existing directories to ``sys.path`` for this process."""
    added: list[str] = []
    for path in reversed(configured_sdk_paths(settings)):
        if path not in sys.path:
            sys.path.insert(0, path)
            added.append(path)
    return added


@contextmanager
def temporary_sys_path(paths: list[str]) -> Iterator[None]:
    before = list(sys.path)
    try:
        for path in reversed([str(Path(p).resolve()) for p in paths if p and Path(p).exists()]):
            if path not in sys.path:
                sys.path.insert(0, path)
        yield
    finally:
        sys.path[:] = before


def get_python_runtime_info(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    version = sys.version_info
    runtime = {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "major": version.major,
        "minor": version.minor,
        "architecture": f"{struct.calcsize('P') * 8}-bit",
        "platform": platform.system() or sys.platform,
        "platform_detail": platform.platform(),
        "sys_prefix": sys.prefix,
        "base_prefix": getattr(sys, "base_prefix", sys.prefix),
        "site_packages": _site_packages(),
        "inside_venv": sys.prefix != getattr(sys, "base_prefix", sys.prefix),
        "inside_conda": bool(sys.prefix and ("conda" in sys.prefix.lower() or "CONDA_PREFIX" in __import__("os").environ)),
    }
    paths = configured_sdk_paths(settings)
    with temporary_sys_path(paths):
        runtime["fbx_importable"] = importlib.util.find_spec("fbx") is not None
        runtime["fbxcommon_importable"] = importlib.util.find_spec("FbxCommon") is not None
    runtime["configured_paths"] = paths
    return runtime


def test_fbx_sdk_configuration(paths: dict[str, Any] | list[str] | None) -> FbxSdkTestResult:
    if isinstance(paths, dict):
        test_paths = configured_sdk_paths(paths)
    else:
        test_paths = [str(Path(path).resolve()) for path in (paths or []) if path and Path(path).exists()]
    result = FbxSdkTestResult(tested_paths=test_paths)
    with temporary_sys_path(test_paths):
        try:
            importlib.invalidate_caches()
            fbx = importlib.import_module("fbx")
            result.fbx_import_ok = True
            try:
                importlib.import_module("FbxCommon")
                result.fbxcommon_import_ok = True
            except Exception:
                result.fbxcommon_import_ok = False
            manager_cls = getattr(fbx, "FbxManager", getattr(fbx, "KFbxSdkManager", None))
            scene_cls = getattr(fbx, "FbxScene", getattr(fbx, "KFbxScene", None))
            if manager_cls is None or scene_cls is None:
                raise RuntimeError("fbx module imported, but FbxManager/FbxScene classes were not found.")
            manager = manager_cls.Create()
            result.manager_create_ok = manager is not None
            if manager is None:
                raise RuntimeError("FbxManager.Create() returned None.")
            try:
                version_fn = getattr(manager, "GetVersion", None)
                if callable(version_fn):
                    result.detected_sdk_version = str(version_fn())
                scene = scene_cls.Create(manager, "GhostRiggerFbxSdkTest")
                result.scene_create_ok = scene is not None
                if scene is not None and hasattr(scene, "Destroy"):
                    scene.Destroy()
            finally:
                if hasattr(manager, "Destroy"):
                    manager.Destroy()
            result.success = result.fbx_import_ok and result.manager_create_ok and result.scene_create_ok
        except Exception as exc:
            result.error_message = f"{type(exc).__name__}: {exc}"
            result.traceback_text = traceback.format_exc()
            result.recommended_fix = _recommended_fix(result.error_message)
    if not result.success and not result.recommended_fix:
        result.recommended_fix = _recommended_fix(result.error_message)
    return result


def likely_sdk_files(path: str | Path) -> dict[str, list[str]]:
    root = Path(path).expanduser()
    found = {"bindings": [], "fbxcommon": [], "libraries": []}
    if not root.exists():
        return found
    binary_names = {"Windows": ("fbx.pyd",), "Linux": ("fbx.so",), "Darwin": ("fbx.so", "fbx.dylib")}
    wanted = binary_names.get(platform.system(), ("fbx.pyd", "fbx.so", "fbx.dylib"))
    try:
        for candidate in root.rglob("*"):
            lower = candidate.name.lower()
            if lower in {item.lower() for item in wanted}:
                found["bindings"].append(str(candidate))
            elif lower == "fbxcommon.py":
                found["fbxcommon"].append(str(candidate))
            elif lower.startswith(("libfbxsdk", "fbxsdk")) and candidate.suffix.lower() in {".dll", ".so", ".dylib"}:
                found["libraries"].append(str(candidate))
    except OSError:
        pass
    return found


def load_fbx_settings_from_file(settings_path: str | Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(settings_path).read_text(encoding="utf-8"))
    except Exception:
        data = {}
    return normalize_fbx_sdk_settings(data.get("fbx_sdk") or {})


def _site_packages() -> list[str]:
    paths: list[str] = []
    for getter in (site.getsitepackages, lambda: [site.getusersitepackages()]):
        try:
            for value in getter():
                if value and value not in paths:
                    paths.append(value)
        except Exception:
            pass
    return paths


def _recommended_fix(error: str) -> str:
    lower = str(error or "").lower()
    if "dll" in lower or "specified module" in lower or "shared object" in lower:
        return "The binding was found but a required Autodesk FBX SDK library could not be loaded. Add the SDK binary/library folder for the same platform and architecture."
    if "bad magic" in lower or "wrong architecture" in lower or "%1 is not" in lower:
        return "The selected FBX binding appears to target a different Python ABI or architecture. Choose bindings matching this Python major/minor version and 64-bit/32-bit architecture."
    if "no module named" in lower:
        return "Select the folder containing Autodesk's fbx binary module and, if separate, the folder containing FbxCommon.py."
    return "Download Autodesk FBX Python SDK from Autodesk, then select binding paths matching this Python version and platform."
