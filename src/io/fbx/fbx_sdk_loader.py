"""Safe optional loader for Autodesk Python FBX SDK bindings."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import sys
from types import ModuleType


@dataclass(frozen=True)
class FbxSdkModules:
    fbx: ModuleType | None
    FbxCommon: ModuleType | None
    fbx_error: str = ""
    common_error: str = ""

    @property
    def available(self) -> bool:
        return self.fbx is not None


_CACHE: FbxSdkModules | None = None


def _import_optional_module(name: str) -> tuple[ModuleType | None, str]:
    try:
        return importlib.import_module(name), ""
    except Exception as exc:  # Autodesk bindings can fail with DLL load errors.
        return None, f"{type(exc).__name__}: {exc}"


def get_fbx_modules(refresh: bool = False) -> FbxSdkModules:
    """Return loaded FBX modules without raising when the SDK is missing."""
    global _CACHE
    if _CACHE is not None and not refresh:
        return _CACHE
    fbx, fbx_error = _import_optional_module("fbx")
    common, common_error = _import_optional_module("FbxCommon")
    _CACHE = FbxSdkModules(fbx=fbx, FbxCommon=common, fbx_error=fbx_error, common_error=common_error)
    return _CACHE


def is_fbx_sdk_available() -> bool:
    """Return True when Autodesk's ``fbx`` Python module is importable."""
    return get_fbx_modules().available


def get_fbx_sdk_status() -> str:
    """Human-readable SDK availability summary for UI dialogs and logs."""
    modules = get_fbx_modules(refresh=True)
    lines = [
        "Autodesk FBX Python SDK status:",
        f"Python executable: {sys.executable}",
        f"fbx module: {'available' if modules.fbx else 'missing'}",
        f"FbxCommon.py: {'available' if modules.FbxCommon else 'missing'}",
    ]
    if modules.fbx_error:
        lines.append(f"fbx import error: {modules.fbx_error}")
    if modules.common_error:
        lines.append(f"FbxCommon import error: {modules.common_error}")
    if modules.fbx is not None:
        version = _detect_sdk_version(modules.fbx)
        if version:
            lines.append(f"Detected SDK version: {version}")
    if not modules.available:
        lines.extend(
            [
                "",
                "Autodesk FBX Python SDK is not installed or not visible to this Python environment.",
                "Install Autodesk FBX Python SDK bindings matching this Python version and platform,",
                "then ensure fbx and FbxCommon.py are on PYTHONPATH.",
            ]
        )
    return "\n".join(lines)


def _detect_sdk_version(fbx: ModuleType) -> str:
    manager = None
    try:
        manager_cls = getattr(fbx, "FbxManager", getattr(fbx, "KFbxSdkManager", None))
        if manager_cls is None:
            return ""
        manager = manager_cls.Create()
        version_fn = getattr(manager, "GetVersion", None)
        if callable(version_fn):
            return str(version_fn())
        return str(getattr(fbx, "FBXSDK_VERSION_STRING", "") or "")
    except Exception:
        return str(getattr(fbx, "FBXSDK_VERSION_STRING", "") or "")
    finally:
        if manager is not None:
            destroy = getattr(manager, "Destroy", None)
            if callable(destroy):
                destroy()

