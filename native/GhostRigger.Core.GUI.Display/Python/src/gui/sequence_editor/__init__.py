"""Qt widgets for the GhostRigger Sequence Editor."""

from .sequence_editor_window import SequenceEditorWindow

__all__ = ["SequenceEditorWindow"]
"""GhostRigger sequence editor package."""

from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)
