"""Blender integration module for HolocronToolset.

This module provides functionality to use Blender as an alternative 3D editor
for the Module Designer, Indoor Map Builder, and GIT Editor, replacing the
built-in PyKotorGL Scene renderer.

Architecture:
- detection.py: Blender installation detection
- ipc_client.py: JSON-RPC IPC client for communicating with Blender
- serializers.py: Serialize GIT, LYT, Module data for IPC
- commands.py: Command definitions for Blender operations
- integration.py: Mixin classes for editor integration
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from toolset.blender.detection import (
    BlenderInfo,
    BlenderSettings,
    check_kotorblender_installed,
    detect_blender,
    find_all_blender_installations,
    find_blender_executable,
    get_blender_settings,
    get_blender_version,
    install_kotorblender,
    is_blender_available,
    launch_blender_with_ipc,
    uninstall_kotorblender,
)
from toolset.blender.ipc_client import (
    BlenderCommands,
    BlenderIPCClient,
    ConnectionState,
    get_ipc_client,
)

__all__ = [
    # Detection
    "BlenderInfo",
    "BlenderSettings",
    "check_kotorblender_installed",
    "detect_blender",
    "find_all_blender_installations",
    "find_blender_executable",
    "get_blender_settings",
    "get_blender_version",
    "install_kotorblender",
    "is_blender_available",
    "launch_blender_with_ipc",
    "uninstall_kotorblender",
    # Integration
    "BlenderEditorMixin",
    "check_blender_and_ask",
    # Commands
    "BlenderEditorController",
    "BlenderEditorMode",
    "BlenderSession",
    "get_blender_controller",
    # IPC
    "BlenderCommands",
    "BlenderIPCClient",
    "ConnectionState",
    "get_ipc_client",
]

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "BlenderEditorMixin": ("toolset.blender.integration", "BlenderEditorMixin"),
    "check_blender_and_ask": ("toolset.blender.integration", "check_blender_and_ask"),
    "BlenderEditorController": ("toolset.blender.commands", "BlenderEditorController"),
    "BlenderEditorMode": ("toolset.blender.commands", "BlenderEditorMode"),
    "BlenderSession": ("toolset.blender.commands", "BlenderSession"),
    "get_blender_controller": ("toolset.blender.commands", "get_blender_controller"),
}


def __getattr__(name: str) -> Any:
    """Lazily resolve heavier Blender integration exports.

    The editors often need detection/settings helpers even when the live Blender
    bridge is unavailable. Delaying imports keeps package import cheap and
    prevents one broken integration submodule from poisoning the entire package.
    """

    if name not in _LAZY_EXPORTS:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)

    module_name, attr_name = _LAZY_EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
