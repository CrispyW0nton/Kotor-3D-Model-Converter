"""GhostRigger cinematic sequence system."""

from . import tracks as _tracks  # noqa: F401 - registers built-in track types
from .animation_preview import AnimationPreviewTarget, build_preview_target, iter_scene_preview_targets, tag_pose_for_preview_target
from .sequence_binding import SequenceBinding, SequenceBindingType, SequenceTargetType
from .sequence_evaluator import SequenceEvaluator, SceneObjectResolver
from .sequence_keyframe import InterpolationMode, SequenceKeyframe
from .sequence_manager import SequenceManager, ensure_sequence_object_id, infer_target_type
from .sequence_model import GhostRiggerLevelSequence, SequenceMarker, SequenceTime
from .sequence_playback import SequencePlaybackController
from .sequence_runtime import CharacterSequenceRuntimeState, RootTransformController, ViewportInterpolationState
from .sequence_serialization import load_sequence_file, save_sequence_file
from .sequence_track import SequenceTrack

__all__ = [
    "AnimationPreviewTarget",
    "CharacterSequenceRuntimeState",
    "GhostRiggerLevelSequence",
    "InterpolationMode",
    "RootTransformController",
    "SceneObjectResolver",
    "SequenceBinding",
    "SequenceBindingType",
    "SequenceEvaluator",
    "SequenceKeyframe",
    "SequenceManager",
    "SequenceMarker",
    "SequencePlaybackController",
    "SequenceTargetType",
    "SequenceTime",
    "SequenceTrack",
    "ViewportInterpolationState",
    "build_preview_target",
    "ensure_sequence_object_id",
    "infer_target_type",
    "iter_scene_preview_targets",
    "load_sequence_file",
    "save_sequence_file",
    "tag_pose_for_preview_target",
]
