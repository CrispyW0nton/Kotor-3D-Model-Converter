"""Viewport widget specializations for owning GhostRigger workbenches."""

from __future__ import annotations

from PySide6 import QtCore

from .viewport_widget import QtViewportWidget


class QtMainViewportWidget(QtViewportWidget):
    """Main application viewport with main-window defaults."""

    VIEWPORT_ROLE = "main"
    DEFAULT_THUMBNAIL_ENABLED = False


class QtMapStudioViewportWidget(QtViewportWidget):
    """Map Studio viewport with KMAP-only Modeling and Blockout chrome."""

    VIEWPORT_ROLE = "map_studio"
    DEFAULT_MAP_STUDIO_AUTHORING_CHROME = True


class QtCharacterBuilderViewportWidget(QtViewportWidget):
    """Character Builder viewport with builder-specific HUD affordances."""

    rigTransformMarkingMenuRequested = QtCore.Signal(QtCore.QPoint)
    rigToolsMarkingMenuRequested = QtCore.Signal(QtCore.QPoint)

    VIEWPORT_ROLE = "character_builder"
    DEFAULT_THUMBNAIL_ENABLED = True
    DEFAULT_VIEWPORT_TOOLBAR_VISIBLE = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mesh_transform_promotes_to_model_root = True

    @staticmethod
    def _event_global_position(event, fallback_widget=None) -> QtCore.QPoint:
        global_pos = getattr(event, "globalPosition", lambda: None)()
        if global_pos is not None:
            return global_pos.toPoint()
        global_pos = getattr(event, "globalPos", lambda: None)()
        if global_pos is not None:
            return global_pos
        position = getattr(event, "position", lambda: None)()
        if position is not None and fallback_widget is not None:
            return fallback_widget.mapToGlobal(position.toPoint())
        pos = getattr(event, "pos", lambda: None)()
        if pos is not None and fallback_widget is not None:
            return fallback_widget.mapToGlobal(pos)
        return QtCore.QPoint()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt API
        if event.type() == QtCore.QEvent.MouseButtonPress:
            button = getattr(event, "button", lambda: None)()
            if button == QtCore.Qt.RightButton:
                focus = getattr(watched, "setFocus", None)
                if callable(focus):
                    focus()
                modifiers = getattr(event, "modifiers", lambda: QtCore.Qt.NoModifier)()
                global_pos = self._event_global_position(event, watched)
                if bool(modifiers & QtCore.Qt.ShiftModifier):
                    self.rigToolsMarkingMenuRequested.emit(global_pos)
                else:
                    self.rigTransformMarkingMenuRequested.emit(global_pos)
                return True
        return super().eventFilter(watched, event)


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
    "QtMapStudioViewportWidget",
    "QtCharacterBuilderViewportWidget",
    "QtRetargetViewportWidget",
    "QtUnrealAnimatorViewportWidget",
)
