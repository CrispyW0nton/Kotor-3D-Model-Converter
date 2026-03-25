"""Scene monitoring hooks for the Holocron Toolset Blender bridge."""

from __future__ import annotations

from .server import HolocronIPCServer


def start_scene_monitor(server: HolocronIPCServer) -> None:
    """Start polling the Blender scene for selection and transform changes."""
    server.start_scene_monitor()
