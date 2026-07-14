from __future__ import annotations

import json
from pathlib import Path
from types import MethodType, SimpleNamespace

import pytest

from src.core.characters.rig_session import (
    RIG_SESSION_METADATA_KEY,
    RIG_SESSION_SCHEMA,
    RIG_SESSION_SCHEMA_VERSION,
    RigSession,
    RigStage,
    RigStageStatus,
)


ROOT = Path(__file__).resolve().parents[1]
CHARACTER_BUILDER_MIRRORS = (
    ROOT
    / "native"
    / "GhostRigger.Core.GUI.Display"
    / "Python"
    / "src"
    / "gui"
    / "panels"
    / "qt_character_builder_panel.py",
    ROOT
    / "native"
    / "GhostRigger.Core.Tools"
    / "Python"
    / "src"
    / "gui"
    / "panels"
    / "qt_character_builder_panel.py",
)


def test_rig_session_has_stable_schema_id_and_all_stage_revisions() -> None:
    session = RigSession()
    session_id = session.session_id

    source = session.complete_stage(
        RigStage.SOURCE,
        {"source_path": Path("mesh.fbx"), "bounds": (1.0, 2.0, 3.0)},
    )
    body = session.complete_stage(
        RigStage.BODY_LANDMARKS,
        {"guides": {"hip": {"position": (0.0, 0.0, 1.0)}}},
    )

    payload = session.to_dict()
    encoded = json.dumps(payload, allow_nan=False)
    restored = RigSession.from_dict(json.loads(encoded))

    assert payload["schema"] == RIG_SESSION_SCHEMA
    assert payload["schema_version"] == RIG_SESSION_SCHEMA_VERSION
    assert set(payload["stages"]) == {stage.value for stage in RigStage}
    assert source.input_revision == 0
    assert source.output_revision == 1
    assert body.input_revision == 1
    assert body.output_revision == 2
    assert restored.session_id == session_id
    assert restored.state(RigStage.BODY_LANDMARKS).artifact["guides"]["hip"]["position"] == [0.0, 0.0, 1.0]

    payload["revision"] = 0  # tolerate an older writer that omitted the counter
    repaired = RigSession.from_dict(payload)
    assert repaired.complete_stage("fingers", {"guides": {}}).output_revision == 3


def test_landmark_revisions_invalidate_only_real_downstream_dependants() -> None:
    session = RigSession()
    session.complete_stage("source", {"mesh": "body"})
    session.complete_stage("body_landmarks", {"guides": {"hip": {}}})
    session.complete_stage("fingers", {"guides": {"lhand": {}}})
    session.complete_stage("skeleton", {"bones": 42})
    session.complete_stage("correspondence", {"mapped": 42})
    session.complete_stage("weights", {"weighted": 100})
    session.complete_stage("bind", {"pose": "baked"})
    session.complete_stage("export", {"mdl": "pmbam.mdl"})
    finger_revision = session.state("fingers").output_revision

    body = session.complete_stage("body_landmarks", {"guides": {"hip": {"x": 1}}})

    assert session.state("body_landmarks").valid
    assert session.state("fingers").status is RigStageStatus.VALID
    assert session.state("fingers").output_revision == finger_revision
    for stage in ("skeleton", "correspondence", "weights", "bind", "export"):
        state = session.state(stage)
        assert state.status is RigStageStatus.STALE
        assert state.invalidated_by == "body_landmarks"
        assert state.invalidated_revision == body.output_revision
        assert state.has_preserved_output


def test_failed_and_cancelled_retries_preserve_last_valid_output() -> None:
    session = RigSession()
    session.complete_stage("source", {"mesh": "body"})
    state = session.complete_stage("body_landmarks", {"guides": {"hip": {"x": 1}}})
    original_revision = state.output_revision
    original_artifact = dict(state.artifact)

    session.start_stage("body_landmarks", cancellable=True, job_id="body-job")
    assert session.state("body_landmarks").running
    assert session.state("body_landmarks").cancellable
    assert session.state("body_landmarks").can_cancel
    session.cancel_stage("body_landmarks", "User cancelled detection.")
    cancelled = session.state("body_landmarks")
    assert cancelled.status is RigStageStatus.CANCELLED
    assert cancelled.output_revision == original_revision
    assert cancelled.artifact == original_artifact

    session.start_stage("body_landmarks")
    session.fail_stage("body_landmarks", "Detector failed.")
    failed = session.state("body_landmarks")
    assert failed.failed
    assert failed.output_revision == original_revision
    assert failed.artifact == original_artifact


def test_running_job_restores_as_interrupted_failure_and_rejects_runtime_blobs() -> None:
    session = RigSession()
    session.start_stage("weights", cancellable=True, job_id="weight-job")
    restored = RigSession.from_dict(session.to_dict())

    state = restored.state("weights")
    assert state.failed
    assert not state.cancellable
    assert not state.job_id
    assert "interrupted" in state.error.lower()

    with pytest.raises(TypeError, match="runtime objects"):
        session.complete_stage("source", {"model": object()})
    with pytest.raises(ValueError, match="non-finite"):
        session.complete_stage("source", {"scale": float("nan")})


def test_character_scene_json_round_trip_preserves_rig_session_metadata() -> None:
    from src.core.geometry.model_data import CharacterScene

    scene = CharacterScene(game_version="K2", character_name="Rig Session Proof")
    session = RigSession()
    session.complete_stage("source", {"source_path": "body.fbx"})
    session.store_in_metadata(scene.metadata)

    restored_scene = CharacterScene.from_json(scene.to_json())
    restored_session = RigSession.restore_from_metadata(restored_scene.metadata)

    assert restored_session.session_id == session.session_id
    assert restored_session.state("source").valid
    assert restored_session.state("source").artifact["source_path"] == "body.fbx"


def _rig_window_harness(window_type, scene):
    harness = SimpleNamespace(scene=scene, _rig_session=None)
    harness._rig_session_module = lambda: __import__(
        "src.core.characters.rig_session", fromlist=["rig_session"]
    )
    for name in (
        "_restore_rig_session_from_scene",
        "_sync_rig_session_metadata",
        "_start_rig_stage",
        "_fail_rig_stage",
        "_complete_rig_stage",
    ):
        setattr(harness, name, MethodType(getattr(window_type, name), harness))
    return harness


def test_character_builder_window_stores_and_restores_rig_session_in_scene_metadata() -> None:
    from src.gui.qt_lib.panels.qt_character_builder_panel import QtCharacterBuilderWindow

    scene = SimpleNamespace(metadata={}, dirty=False)
    first = _rig_window_harness(QtCharacterBuilderWindow, scene)
    session = first._restore_rig_session_from_scene()
    first._complete_rig_stage("source", {"source_path": "body.fbx"})
    first._complete_rig_stage("skeleton", {"template": "pmbam"})

    assert scene.dirty
    assert scene.metadata[RIG_SESSION_METADATA_KEY]["session_id"] == session.session_id
    serialized = json.loads(json.dumps(scene.metadata))

    restored_scene = SimpleNamespace(metadata=serialized, dirty=False)
    second = _rig_window_harness(QtCharacterBuilderWindow, restored_scene)
    restored = second._restore_rig_session_from_scene()
    assert restored.session_id == session.session_id
    assert restored.state("source").valid
    assert restored.state("skeleton").artifact["template"] == "pmbam"


def test_character_builder_restores_saved_body_and_finger_guide_values() -> None:
    from src.gui.qt_lib.panels.qt_character_builder_panel import QtCharacterBuilderWindow

    session = RigSession()
    session.complete_stage("source", {"source_path": "body.fbx"})
    session.complete_stage(
        "body_landmarks",
        {
            "guides": {
                "hip": {
                    "position": [0.0, 0.0, 1.0],
                    "bone_parent": "root",
                    "locked": True,
                    "mirror_of": None,
                    "colour": [255, 200, 0],
                },
                "lhand": {
                    "position": [-1.0, 0.0, 1.0],
                    "bone_parent": "lforearm",
                    "locked": False,
                    "mirror_of": None,
                    "colour": [255, 200, 0],
                },
            }
        },
    )
    session.complete_stage(
        "fingers",
        {
            "guides": {
                "lhand": {
                    "position": [-1.25, 0.0, 1.1],
                    "bone_parent": "lforearm",
                    "locked": True,
                    "mirror_of": None,
                    "colour": [10, 20, 30],
                }
            },
            "masked_bones": ["lfinger01"],
        },
    )
    metadata = {}
    session.store_in_metadata(metadata)
    scene = SimpleNamespace(metadata=metadata, dirty=False)
    window = _rig_window_harness(QtCharacterBuilderWindow, scene)
    window._restore_body_guides_from_rig_session = MethodType(
        QtCharacterBuilderWindow._restore_body_guides_from_rig_session,
        window,
    )
    window._push_body_guides_to_viewport = lambda: None
    masks = []
    window.inspector = SimpleNamespace(
        set_hand_masked_bones=lambda values: masks.extend(values)
    )
    window._restore_rig_session_from_scene()

    assert window._restore_body_guides_from_rig_session()
    assert window._body_guides["hip"].position == (0.0, 0.0, 1.0)
    assert window._body_guides["lhand"].position == (-1.25, 0.0, 1.1)
    assert window._body_guides["lhand"].locked
    assert window._acurig.mask.is_masked("lfinger01")
    assert masks == ["lfinger01"]

    # A new source revision makes old landmarks inspectable but unsafe to
    # restore onto the replacement mesh.
    session.complete_stage("source", {"source_path": "replacement.fbx"})
    window._rig_session = session
    assert not window._restore_body_guides_from_rig_session()
    assert window._body_guides == {}


def test_character_builder_mirrors_wire_only_existing_rig_stage_boundaries() -> None:
    required_source_fragments = (
        'self._start_rig_stage("source")',
        'self._body_landmark_artifact("place_body_guides")',
        'self._finger_artifact(',
        'self._start_rig_stage("skeleton")',
        '"kind": "native_kotor_template"',
        '"kind": "legacy_acurig_auto_skin"',
        'self._start_rig_stage("export")',
        "self._restore_body_guides_from_rig_session()",
        "self._sync_rig_session_metadata(mark_dirty=False)",
    )
    unsupported_claims = (
        'self._complete_rig_stage("correspondence"',
        'self._complete_rig_stage("bind"',
    )

    assert CHARACTER_BUILDER_MIRRORS[0].read_bytes() == CHARACTER_BUILDER_MIRRORS[1].read_bytes()

    for path in CHARACTER_BUILDER_MIRRORS:
        source = path.read_text(encoding="utf-8")
        for fragment in required_source_fragments:
            assert fragment in source, f"{path.name} missing {fragment}"
        for fragment in unsupported_claims:
            assert fragment not in source, f"{path.name} invents unsupported stage output"
