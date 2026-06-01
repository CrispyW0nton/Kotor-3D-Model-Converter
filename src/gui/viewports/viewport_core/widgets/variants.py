"""Viewport widget specializations for owning GhostRigger workbenches."""

from __future__ import annotations

from .viewport_widget import QtViewportWidget


class QtMainViewportWidget(QtViewportWidget):
    """Main application viewport with main-window defaults."""

    VIEWPORT_ROLE = "main"
    DEFAULT_THUMBNAIL_ENABLED = False


class QtCharacterBuilderViewportWidget(QtViewportWidget):
    """Character Builder viewport with builder-specific HUD affordances."""

    VIEWPORT_ROLE = "character_builder"
    DEFAULT_THUMBNAIL_ENABLED = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mesh_transform_promotes_to_model_root = True


class QtRetargetViewportWidget(QtViewportWidget):
    """Animation retargeting viewport with workbench-specific defaults."""

    VIEWPORT_ROLE = "retarget"
    DEFAULT_THUMBNAIL_ENABLED = False
    DEFAULT_VIEWPORT_TOOLBAR_VISIBLE = False
    DEFAULT_VIEWCUBE_VISIBLE = False
    DEFAULT_TRANSFORM_TYPEIN_VISIBLE = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Retarget playback may drive a large imported FBX skin on every frame.
        # Mesh hover picking walks projected/skinned triangles, so suspend it
        # only while an animation pose is live. Static pause/inspection still
        # keeps the normal hover affordance.
        self._suspend_mesh_hover_during_animation = True


class QtUnrealAnimatorViewportWidget(QtViewportWidget):
    """Unreal Animator viewport with compact controls for split-pane layouts."""

    VIEWPORT_ROLE = "unreal_animator"
    DEFAULT_THUMBNAIL_ENABLED = False
    DEFAULT_COMPACT_CONTROLS = True

__all__ = (
    "QtMainViewportWidget",
    "QtCharacterBuilderViewportWidget",
    "QtRetargetViewportWidget",
    "QtUnrealAnimatorViewportWidget",
)
