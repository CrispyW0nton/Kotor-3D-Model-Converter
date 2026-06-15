"""Autodesk FBX SDK bridge.

The modules in this package are intentionally optional: importing them must not
require Autodesk's Python FBX bindings to be installed.
"""

from .fbx_sdk_loader import (
    FbxSdkModules,
    configure_fbx_sdk_paths,
    get_fbx_modules,
    get_fbx_sdk_status,
    is_fbx_sdk_available,
)

__all__ = [
    "FbxSdkModules",
    "configure_fbx_sdk_paths",
    "get_fbx_modules",
    "get_fbx_sdk_status",
    "is_fbx_sdk_available",
]
