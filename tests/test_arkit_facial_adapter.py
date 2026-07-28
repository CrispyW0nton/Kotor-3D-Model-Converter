"""Focused contracts for Audio2Face/MediaPipe ARKit facial input."""

from __future__ import annotations

import json

import pytest

from src.adapters.facial.arkit_performance import (
    ARKIT_BLENDSHAPE_NAMES,
    arkit_to_kotor_weights,
    best_kotor_viseme,
    clip_from_blendshape_frames,
    load_audio2face_json,
)
from src.core.animation.facial_performance import FacialSource


def test_matrix_frames_become_a_normalized_audio2face_clip() -> None:
    clip = clip_from_blendshape_frames(
        ("jaw_open", "mouthPucker", "eyeBlink_L"),
        ((0.0, 0.0, 0.0), (1.2, 0.75, 0.5)),
        frame_rate=30.0,
        source=FacialSource.AUDIO2FACE,
    )

    assert clip.source is FacialSource.AUDIO2FACE
    assert clip.duration == pytest.approx(1.0 / 30.0)
    assert clip.frames[1].channels == {
        "jawOpen": 1.0,
        "mouthPucker": 0.75,
        "eyeBlinkLeft": 0.5,
    }


def test_audio2face_json_accepts_exported_names_weights_and_timestamps(
    tmp_path,
) -> None:
    target = tmp_path / "xaria-a2f.json"
    target.write_text(
        json.dumps(
            {
                "blendShapeNames": ["jawOpen", "mouthFunnel"],
                "weights": [[0.0, 0.0], [0.8, 0.9]],
                "timestamps": [0.0, 0.2],
                "frameRate": 60,
            }
        ),
        encoding="utf-8",
    )

    clip = load_audio2face_json(target)

    assert clip.duration == pytest.approx(0.2)
    assert clip.sample(0.1)["jawOpen"] == pytest.approx(0.4)
    assert clip.metadata["adapter"] == "audio2face_arkit_json"


def test_arkit_projection_preserves_open_round_and_closed_mouth_intent() -> None:
    ah = arkit_to_kotor_weights({"jawOpen": 1.0})
    oh = arkit_to_kotor_weights(
        {"jawOpen": 0.7, "mouthFunnel": 1.0}
    )
    closed = arkit_to_kotor_weights(
        {"mouthClose": 1.0, "mouthPressLeft": 0.8, "mouthPressRight": 0.8}
    )

    assert best_kotor_viseme(ah) == 3
    assert best_kotor_viseme(oh) == 4
    assert best_kotor_viseme(closed) == 11
    assert len(ARKIT_BLENDSHAPE_NAMES) == 52
