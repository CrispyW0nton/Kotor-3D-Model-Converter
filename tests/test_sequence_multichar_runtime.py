from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
for path in reversed(
    (
        ROOT / "native/GhostRigger.Core.Tools/Python",
        ROOT / "native/GhostRigger.Core.Math/Python",
        ROOT / "native/GhostRigger.Core.Rendering/Python",
    )
):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)


from src.core.rendering.mesh_render_data import ScopedAnimationPoseSet, _pose_node_for_transform
from src.sequence.sequence_binding import SequenceBinding, SequenceTargetType
from src.sequence.sequence_evaluator import SequenceEvaluator
from src.sequence.sequence_model import GhostRiggerLevelSequence
from src.sequence.tracks.character_track import CharacterTrack
from src.sequence.tracks.transform_track import TransformTrack


class FakeNode:
    def __init__(self, name: str, index: int, *, object_id: str = "", source_id: int = 0):
        self.name = name
        self.index = index
        self.position = (0.0, 0.0, 0.0)
        self.rotation = (0.0, 0.0, 0.0, 1.0)
        self.children = []
        self.parent = None
        self._gr_scene_object_id = object_id
        self._gr_source_model_id = source_id


class FakeModel:
    def __init__(self, name: str, object_id: str, source_id: int):
        self.name = name
        self.supermodel = ""
        self.anim_scale = 1.0
        self.animations = [
            SimpleNamespace(name="walk", length=2.0),
            SimpleNamespace(name="run", length=2.0),
            SimpleNamespace(name="look_left", length=1.0),
        ]
        self.root_node = FakeNode("root", 0, object_id=object_id, source_id=source_id)
        self.head_node = FakeNode("head", 1, object_id=object_id, source_id=source_id)
        self.head_node.parent = self.root_node
        self.root_node.children.append(self.head_node)

    def all_nodes(self):
        return [self.root_node, self.head_node]


class FakeSceneManager:
    def __init__(self, objects):
        self._objects = list(objects)

    def get_scene_objects(self):
        return list(self._objects)


class FakeViewport:
    def __init__(self, objects):
        self.character_poses = {}
        self.pose_metadata = {}
        self.refresh_count = 0
        self.render_count = 0
        self.model = None
        self.camera_manager = None
        self.scene_manager = FakeSceneManager(objects)

    def parent(self):
        return self

    def set_character_animation_pose(self, character_instance_id, pose, name="", time=0.0, length=0.0):
        if pose is None:
            self.character_poses.pop(str(character_instance_id), None)
            self.pose_metadata.pop(str(character_instance_id), None)
            return
        self.character_poses[str(character_instance_id)] = pose
        self.pose_metadata[str(character_instance_id)] = (name, time, length)

    def clear_character_animation_pose(self, character_instance_id):
        self.character_poses.pop(str(character_instance_id), None)
        self.pose_metadata.pop(str(character_instance_id), None)

    def refresh_scene_transforms(self, _reason=""):
        self.refresh_count += 1

    def _request_render(self, **_kwargs):
        self.render_count += 1


class FakeAnimationEngine:
    def __init__(self, model):
        self.model = model
        self.current_animation = None
        self.current_time = 0.0

    def play(self, name, loop=True, **_kwargs):
        length = 1.0 if "look" in str(name).lower() else 2.0
        self.current_animation = SimpleNamespace(name=name, length=length, loop=loop)
        return True

    def stop(self):
        pass

    def seek(self, seconds):
        self.current_time = float(seconds)

    def evaluate(self):
        name = str(getattr(self.current_animation, "name", "") or "").lower()
        base = {"walk": 1.0, "run": 10.0, "look_left": 100.0}.get(name, 0.0)
        nodes = {}
        nodes_by_index = {}
        for node in self.model.all_nodes():
            value = base + self.current_time + float(node.index)
            pose_node = SimpleNamespace(
                name=node.name,
                position=(value, 0.0, 0.0),
                rotation=(0.0, 0.0, 0.0, 1.0),
                scale=1.0,
                alpha=None,
                selfillum=None,
            )
            nodes[node.name.lower()] = pose_node
            nodes_by_index[node.index] = pose_node
        pose = SimpleNamespace(time=self.current_time, nodes=nodes)
        pose.nodes_by_index = nodes_by_index
        pose.duplicate_node_names = set()
        return pose


def _install_fake_animation_engine(monkeypatch):
    import src.core  # noqa: F401

    package_paths = []
    existing_pkg = sys.modules.get("src.core.animation")
    package_paths.extend(str(path) for path in getattr(existing_pkg, "__path__", []) or [])
    workflow_animation_path = ROOT / "native/GhostRigger.Core.Workflow/Python/src/core/animation"
    if workflow_animation_path.exists():
        package_paths.append(str(workflow_animation_path))

    animation_pkg = types.ModuleType("src.core.animation")
    animation_pkg.__path__ = list(dict.fromkeys(package_paths))
    engine_module = types.ModuleType("src.core.animation.animation_engine")
    engine_module.AnimationEngine = FakeAnimationEngine
    engine_module.SuperModelResolver = object
    monkeypatch.setitem(sys.modules, "src.core.animation", animation_pkg)
    monkeypatch.setitem(sys.modules, "src.core.animation.animation_engine", engine_module)


def _scene_object(object_id: str, name: str, model: FakeModel):
    return SimpleNamespace(
        id=object_id,
        name=name,
        object_type="model",
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        _gr_scale=(1.0, 1.0, 1.0),
        metadata={"_runtime_model": model, "character_instance_id": object_id},
    )


def _binding(object_id: str, name: str):
    return SequenceBinding(
        display_name=name,
        target_object_id=object_id,
        target_object_name=name,
        target_type=SequenceTargetType.CHARACTER,
        metadata={"character_instance_id": object_id},
    )


def test_multi_character_sequence_evaluation_isolates_runtime_poses(monkeypatch):
    _install_fake_animation_engine(monkeypatch)
    model_a = FakeModel("SharedRig", "char-a", 101)
    model_b = FakeModel("SharedRig", "char-b", 101)
    obj_a = _scene_object("char-a", "Character A", model_a)
    obj_b = _scene_object("char-b", "Character B", model_b)
    viewport = FakeViewport([obj_a, obj_b])
    sequence = GhostRiggerLevelSequence(frame_rate=24, end_frame=96)
    binding_a = sequence.add_binding(_binding("char-a", "Character A"))
    binding_b = sequence.add_binding(_binding("char-b", "Character B"))
    track_a = binding_a.add_track(CharacterTrack(name="Base Locomotion"))
    track_b = binding_b.add_track(CharacterTrack(name="Base Locomotion"))
    track_a.add_animation_key(0, "walk", length=2.0, duration_frames=48, character_instance_id="char-a")

    evaluator = SequenceEvaluator(viewport=viewport, owner=viewport)
    evaluator.evaluate(sequence, frame=12)

    assert set(viewport.character_poses) == {"char-a"}
    pose_a_only = viewport.character_poses["char-a"]
    assert getattr(pose_a_only, "_gr_animation_character_instance_id") == "char-a"
    assert getattr(pose_a_only, "_gr_animation_scene_object_id") == "char-a"

    track_b.add_animation_key(0, "run", length=2.0, duration_frames=48, character_instance_id="char-b")
    evaluator.evaluate(sequence, frame=12)

    assert set(viewport.character_poses) == {"char-a", "char-b"}
    assert viewport.character_poses["char-a"] is not viewport.character_poses["char-b"]
    assert viewport.character_poses["char-a"].nodes["root"].position[0] != viewport.character_poses["char-b"].nodes["root"].position[0]
    assert getattr(viewport.character_poses["char-b"], "_gr_animation_character_instance_id") == "char-b"
    assert len(evaluator._character_runtime_states) == 2
    assert evaluator._character_runtime_states["char-a"].viewport_interpolation.pose is viewport.character_poses["char-a"]
    assert evaluator._character_runtime_states["char-b"].viewport_interpolation.pose is viewport.character_poses["char-b"]


def test_single_character_sequence_uses_main_viewport_animation_dispatch(monkeypatch):
    _install_fake_animation_engine(monkeypatch)
    model = FakeModel("SharedRig", "char-a", 101)
    obj = _scene_object("char-a", "Character A", model)
    viewport = FakeViewport([obj])
    calls = []

    class Owner:
        scene_manager = viewport.scene_manager

        def _apply_viewport_animation_pose(self, pose, *, name="", time=0.0, length=0.0, reason=""):
            calls.append((pose, name, time, length, reason))
            return True

    sequence = GhostRiggerLevelSequence(frame_rate=24, end_frame=96)
    binding = sequence.add_binding(_binding("char-a", "Character A"))
    track = binding.add_track(CharacterTrack(name="Base Locomotion"))
    track.add_animation_key(0, "walk", length=2.0, duration_frames=48, character_instance_id="char-a")

    evaluator = SequenceEvaluator(viewport=viewport, owner=Owner())
    evaluator.evaluate(sequence, frame=12)

    assert calls
    pose, name, time_value, length, reason = calls[-1]
    assert name == "walk"
    assert reason == "sequence playback"
    assert length == 2.0
    assert time_value == 0.5
    assert pose is evaluator._character_runtime_states["char-a"].viewport_interpolation.pose
    assert viewport.character_poses == {}


def test_clip_instance_timing_is_non_destructive_and_duplicate_frame_safe():
    sequence = GhostRiggerLevelSequence(frame_rate=24, end_frame=96)
    track = CharacterTrack(name="Base")
    first = track.add_animation_key(0, "walk", length=2.0, duration_frames=48, character_instance_id="char-a")
    second = track.add_animation_key(0, "look_left", length=1.0, duration_frames=24, character_instance_id="char-a", layer_mode="additive")

    assert first is not second
    assert len(track.keyframes) == 2
    assert first.value["source_clip_id"] == "walk"
    assert first.value["clip_start_frame"] == 0
    assert first.value["clip_end_frame"] == 48

    first.selected = True
    track.move_selected_keys(12)

    assert first.frame == 12
    assert first.value["clip_start_frame"] == 12
    assert first.value["clip_end_frame"] == 60
    assert first.value["length"] == 2.0
    assert first.value["source_out_seconds"] == 2.0

    first.value["duration_frames"] = 96
    first.value["clip_end_frame"] = 108
    evaluator = SequenceEvaluator()

    assert evaluator._animation_clip_seconds(sequence, first, 60) == 1.0
    assert first.value["length"] == 2.0
    assert first.value["source_out_seconds"] == 2.0


def test_additive_layer_composes_over_base_pose():
    model = FakeModel("Rig", "char-a", 101)
    evaluator = SequenceEvaluator()
    base_node = SimpleNamespace(name="root", position=(1.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0, 1.0), scale=1.0, alpha=None, selfillum=None)
    add_node = SimpleNamespace(name="root", position=(0.0, 2.0, 0.0), rotation=(0.0, 0.0, 0.0, 1.0), scale=1.0, alpha=None, selfillum=None)
    base_pose = SimpleNamespace(time=0.0, nodes={"root": base_node})
    additive_pose = SimpleNamespace(time=0.0, nodes={"root": add_node})
    base_key = SimpleNamespace(frame=0, value={"animation": "walk", "layer_mode": "base", "weight": 1.0, "duration_frames": 48})
    additive_key = SimpleNamespace(frame=0, value={"animation": "look_left", "layer_mode": "additive", "weight": 0.5, "duration_frames": 48})

    composed = evaluator._compose_animation_poses(
        model,
        [
            {"key": base_key, "name": "walk", "pose": base_pose},
            {"key": additive_key, "name": "look_left", "pose": additive_pose},
        ],
        frame=12,
    )

    assert composed.nodes["root"].position == (1.0, 1.0, 0.0)


def test_transform_track_moves_character_root_without_mutating_clip_instance(monkeypatch):
    _install_fake_animation_engine(monkeypatch)
    model = FakeModel("Rig", "char-a", 101)
    obj = _scene_object("char-a", "Character A", model)
    viewport = FakeViewport([obj])
    sequence = GhostRiggerLevelSequence(frame_rate=24, end_frame=96)
    binding = sequence.add_binding(_binding("char-a", "Character A"))
    anim_track = binding.add_track(CharacterTrack(name="Base"))
    transform_track = binding.add_track(TransformTrack(name="Root Motion Override"))
    clip_key = anim_track.add_animation_key(0, "walk", length=2.0, duration_frames=48, character_instance_id="char-a")
    transform_track.add_transform_key(0, location=(0.0, 0.0, 0.0))
    transform_track.add_transform_key(24, location=(12.0, 0.0, 0.0))

    evaluator = SequenceEvaluator(viewport=viewport, owner=viewport)
    evaluator.evaluate(sequence, frame=24)

    assert obj.position == (12.0, 0.0, 0.0)
    assert "char-a" in viewport.character_poses
    assert clip_key.value["length"] == 2.0
    assert clip_key.value["source_out_seconds"] == 2.0


def test_scoped_pose_set_prevents_matching_bone_names_from_cross_driving():
    node_a = FakeNode("root", 0, object_id="char-a", source_id=101)
    node_b = FakeNode("root", 0, object_id="char-b", source_id=101)
    pose_a_node = SimpleNamespace(name="root", position=(1.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0, 1.0), scale=1.0)
    pose_b_node = SimpleNamespace(name="root", position=(2.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0, 1.0), scale=1.0)
    pose_a = SimpleNamespace(time=0.0, nodes={"root": pose_a_node}, nodes_by_index={0: pose_a_node}, duplicate_node_names=set())
    pose_b = SimpleNamespace(time=0.0, nodes={"root": pose_b_node}, nodes_by_index={0: pose_b_node}, duplicate_node_names=set())
    pose_a._gr_animation_scene_object_id = "char-a"
    pose_b._gr_animation_scene_object_id = "char-b"
    pose_a._gr_animation_source_model_id = 101
    pose_b._gr_animation_source_model_id = 101
    scoped = ScopedAnimationPoseSet({"char-a": pose_a, "char-b": pose_b})

    assert _pose_node_for_transform(node_a, scoped) is pose_a_node
    assert _pose_node_for_transform(node_b, scoped) is pose_b_node


def test_moderngl_scene_animation_uses_node_scoped_skin_and_rigid_transforms():
    source = (
        ROOT
        / "native/GhostRigger.Core.Rendering/Python/src/adapters/rendering/moderngl_renderer_impl.py"
    ).read_text(encoding="utf-8")

    assert "animation_pose_for_node" in source
    assert "_node_anim_pose = animation_pose_for_node(node, anim_pose)" in source
    assert "_pose_node_for_transform(node, _node_anim_pose)" in source
    assert "_acheck_pose = animation_pose_for_node(_acheck, anim_pose)" in source
    assert "_skin_anim_base_pose = (" in source
    assert "anim_base_pose=_skin_anim_base_pose" in source
    assert "_skin_uploaders_by_scope" in source
    assert "item is root or getattr(item, \"_gr_scene_object_root_ref\", None) is root" in source
    assert "_skin_uploader_for_node(node)" in source
    assert "scene_gpu_mat is not None and is_animated and not _nd_is_skin" in source
    assert "vbo_wp = (0.0, 0.0, 0.0)" in source
    assert "_scene_animated_node_draw_mat" in source


def test_animation_ipc_carries_target_scene_object_id():
    server_source = (
        ROOT / "native/GhostRigger.Core.Automation/Python/src/ipc/server.py"
    ).read_text(encoding="utf-8")
    client_source = (
        ROOT / "native/GhostRigger.Core.Automation/Python/src/ipc/client.py"
    ).read_text(encoding="utf-8")

    assert '"target"' in server_source
    assert '"object_id"' in server_source
    assert "self._schedule_callback(cb, command, animation, loop, seek, source, target)" in server_source
    assert '"target": target' in server_source
    assert "target: str = \"\"" in client_source
    assert "object_id: str = \"\"" in client_source
    assert 'payload["target"] = target_id' in client_source
