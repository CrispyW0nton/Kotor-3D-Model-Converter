"""Focused contracts for the shared facial-performance pipeline."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from src.core.animation.facial_performance import (
    CUSTOM_ANIMATION_PATCH_NOTICE,
    FacialChannelFrame,
    FacialOutputMode,
    FacialPerformanceClip,
    FacialSource,
    blend_pose_mappings,
    facial_mode_profile,
    lip_duration,
    phoneme_to_viseme,
    sample_lip_blend,
    slerp_quaternion,
)


def test_canonical_kotor_phonemes_use_the_real_sixteen_shape_indices() -> None:
    assert phoneme_to_viseme("AH") == 3
    assert phoneme_to_viseme("IY") == 1
    assert phoneme_to_viseme("M") == 11
    assert phoneme_to_viseme("F") == 8
    assert phoneme_to_viseme("TH") == 10
    assert phoneme_to_viseme("S") == 7
    assert phoneme_to_viseme("UW") == 5
    assert phoneme_to_viseme("sil") == 0


def test_custom_facial_mode_is_explicitly_patch_required() -> None:
    profile = facial_mode_profile(FacialOutputMode.CUSTOM_PATCH_CURVES)

    assert profile.requires_custom_animation_patch is True
    assert profile.channel_limit > 16
    assert "Custom Animation Patch" in CUSTOM_ANIMATION_PATCH_NOTICE
    assert CUSTOM_ANIMATION_PATCH_NOTICE in profile.notice


def test_vanilla_lip_mode_remains_a_patch_free_fallback() -> None:
    profile = facial_mode_profile(FacialOutputMode.VANILLA_LIP)

    assert profile.requires_custom_animation_patch is False
    assert profile.channel_limit == 16
    assert profile.export_kind == "lip_v1"


def test_lip_sampling_uses_duration_and_interpolates_surrounding_shapes() -> None:
    lip = SimpleNamespace(
        duration=2.5,
        get_shapes=lambda time: (3, 11, 0.25),
    )

    blend = sample_lip_blend(lip, 0.75)

    assert lip_duration(lip) == pytest.approx(2.5)
    assert blend.left_shape == 3
    assert blend.right_shape == 11
    assert blend.factor == pytest.approx(0.25)


def test_lip_duration_accepts_legacy_sound_length() -> None:
    assert lip_duration(SimpleNamespace(sound_length=1.75)) == pytest.approx(1.75)


def test_shortest_path_quaternion_slerp_stays_normalized() -> None:
    left = (0.0, 0.0, 0.0, 1.0)
    # The negative representation is the same rotation. A shortest-path
    # interpolation must not spin through 180 degrees.
    right = (0.0, 0.0, 0.0, -1.0)

    blended = slerp_quaternion(left, right, 0.5)

    assert blended == pytest.approx(left)
    assert math.sqrt(sum(value * value for value in blended)) == pytest.approx(1.0)


def test_pose_blending_lerps_positions_and_slerps_rotations() -> None:
    left = {
        "f_jaw_g": {
            "position": (0.0, 1.0, 2.0),
            "rotation": (0.0, 0.0, 0.0, 1.0),
            "scale": 1.0,
        }
    }
    right = {
        "f_jaw_g": {
            "position": (2.0, 3.0, 4.0),
            "rotation": (0.0, 0.0, 1.0, 0.0),
            "scale": 1.5,
        }
    }

    result = blend_pose_mappings(left, right, 0.5)

    assert result["f_jaw_g"]["position"] == pytest.approx((1.0, 2.0, 3.0))
    assert result["f_jaw_g"]["rotation"] == pytest.approx(
        (0.0, 0.0, math.sqrt(0.5), math.sqrt(0.5))
    )
    assert result["f_jaw_g"]["scale"] == pytest.approx(1.25)


def test_performance_clip_blends_audio_capture_and_manual_facs_channels() -> None:
    audio = FacialPerformanceClip(
        duration=1.0,
        source=FacialSource.AUDIO2FACE,
        frames=(
            FacialChannelFrame(0.0, {"jawOpen": 0.0, "mouthSmileLeft": 0.1}),
            FacialChannelFrame(1.0, {"jawOpen": 1.0, "mouthSmileLeft": 0.3}),
        ),
    )
    capture = FacialPerformanceClip(
        duration=1.0,
        source=FacialSource.MINIFACE_MEDIAPIPE,
        frames=(
            FacialChannelFrame(0.0, {"eyeBlinkLeft": 0.0}),
            FacialChannelFrame(1.0, {"eyeBlinkLeft": 0.8}),
        ),
    )
    manual = FacialPerformanceClip(
        duration=1.0,
        source=FacialSource.OPENFACS,
        frames=(
            FacialChannelFrame(0.0, {"browInnerUp": 0.2}),
            FacialChannelFrame(1.0, {"browInnerUp": 0.2}),
        ),
    )

    combined = FacialPerformanceClip.compose(
        audio=audio,
        capture=capture,
        manual=manual,
    )
    sample = combined.sample(0.5)

    assert sample["jawOpen"] == pytest.approx(0.5)
    assert sample["mouthSmileLeft"] == pytest.approx(0.2)
    assert sample["eyeBlinkLeft"] == pytest.approx(0.4)
    assert sample["browInnerUp"] == pytest.approx(0.2)
    assert combined.metadata["composition"]["audio"] == "audio2face"
