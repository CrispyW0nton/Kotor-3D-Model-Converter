"""Explicit adapter boundary for Qt viewport frame rendering."""

from __future__ import annotations


def create_viewport_frame_renderer(viewport):
    """Create the still-frame renderer that renders through an existing Qt viewport."""
    from src.gui.camera.frame_renderer import FrameRenderer

    return FrameRenderer(viewport)


def create_validation_frame_renderer(model):
    """Create the software validation renderer used by backend capture checks."""
    from src.core.camera.arcball_camera import ArcBallCamera
    from src.core.rendering.frame_core.renderer import FrameRenderer

    renderer = FrameRenderer(ArcBallCamera())
    renderer.show_texture = False
    renderer.show_bones = False
    renderer.show_grid = False
    renderer.show_light_gizmos = False
    renderer.set_model(model)
    return renderer
