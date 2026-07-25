from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


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
    assert scoped.pose_for_node(FakeNode("identityless-room-piece", 2)) is None


def test_moderngl_scene_animation_uses_node_scoped_skin_and_rigid_transforms():
    source = (
        ROOT
        / "native/GhostRigger.Core.Rendering/Python/src/adapters/rendering/moderngl_renderer_impl.py"
    ).read_text(encoding="utf-8")

    assert "animation_pose_for_node" in source
    assert "def _resolved_animation_pose(nd)" in source
    assert "_effective_animation_pose_for_node(" in source
    assert "_node_anim_pose = _resolved_animation_pose(node)" in source
    assert "_pose_node_for_transform(node, _node_anim_pose)" in source
    assert "_acheck_pose = _resolved_animation_pose(_acheck)" in source
    assert "_skin_anim_base_pose = (" in source
    assert "anim_base_pose=_skin_anim_base_pose" in source
    assert "_skin_uploaders_by_scope" in source
    assert "item is root or getattr(item, \"_gr_scene_object_root_ref\", None) is root" in source
    assert "_skin_uploader_for_node(node, _skin_palette_scope)" in source
    assert "self._skin_palette_bytes_for_draw(" in source
    assert "scene_gpu_mat is not None and is_animated and not _nd_is_skin" in source
    assert "vbo_wp = (0.0, 0.0, 0.0)" in source
    assert "_scene_animated_node_draw_mat" in source
    assert "_scene_rigid_gpu_pose" in source
    assert "_dynamic_rigid_vbo = bool(is_animated and not _scene_rigid_gpu_pose)" in source
    assert "_rigid_vbo_mode_changed" in source
    assert "gm.scene_rigid_gpu_pose" in source
    assert "if not _dynamic_rigid_vbo:" in source
    assert "self._mesh_cache[node_id] = gm" in source


def test_moderngl_retained_scene_rigid_pose_reuses_gpu_mesh(monkeypatch) -> None:
    import src.adapters.rendering.moderngl_renderer_impl as renderer_impl

    from src.adapters.rendering.moderngl_renderer import ModernGLRenderer
    from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags

    scene = ModelNode(name="scene", flags=int(NodeFlags.HEADER))
    actor = ModelNode(
        name="actor",
        flags=int(NodeFlags.HEADER),
        parent=scene,
        position=(2.0, 0.0, 0.0),
    )
    actor._gr_scene_object_root = True
    actor._gr_scene_gpu_transform = True
    actor._gr_scene_object_id = "actor-1"
    actor._gr_scene_source_position = (5.0, 0.0, 0.0)
    actor._gr_scene_source_rotation = (0.0, 0.0, 0.0, 1.0)
    mesh = ModelNode(
        name="rigid_part",
        flags=int(NodeFlags.HEADER) | int(NodeFlags.MESH),
        parent=actor,
        vertices=[(-0.7, 0.0, 0.0), (0.7, 0.0, 0.0), (0.0, 0.0, 1.2)],
        normals=[(0.0, -1.0, 0.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)],
        faces=[(0, 1, 2)],
        texture="",
    )
    scene.children = [actor]
    actor.children = [mesh]
    # Transparent geometry is queried during both back-to-front sorting and
    # drawing.  The animated world transform should still be evaluated once.
    mesh.alpha = 0.5
    for node in (actor, mesh):
        node._gr_scene_object_id = "actor-1"
        node._gr_scene_object_root_ref = actor
    model = KotorModel(name="retained-actor-cache-proof", root_node=scene)
    model.classification = "character"

    def scoped_pose(x: float) -> ScopedAnimationPoseSet:
        pose_node = SimpleNamespace(
            name="actor",
            position=(5.0 + x, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0, 1.0),
            scale=1.0,
        )
        pose = SimpleNamespace(
            time=x,
            nodes={"actor": pose_node},
            nodes_by_index={},
            duplicate_node_names=set(),
            _gr_animation_scene_object_id="actor-1",
        )
        return ScopedAnimationPoseSet({"actor-1": pose})

    camera = SimpleNamespace(
        eye=(2.0, -6.0, 2.0),
        target=(2.0, 0.0, 0.5),
        up=(0.0, 0.0, 1.0),
        fov=45.0,
        near=0.01,
        far=100.0,
    )
    renderer = ModernGLRenderer()
    renderer.show_grid = False
    renderer.cull_faces = False
    original_world_transform = renderer_impl._animated_node_world_transform
    transform_calls = []

    def counted_world_transform(node, pose):
        transform_calls.append(node)
        return original_world_transform(node, pose)

    monkeypatch.setattr(
        renderer_impl,
        "_animated_node_world_transform",
        counted_world_transform,
    )
    try:
        first_pose = scoped_pose(0.0)
        second_pose = scoped_pose(1.2)
        first_world, _ = original_world_transform(mesh, first_pose)
        second_world, _ = original_world_transform(mesh, second_pose)
        assert first_world == pytest.approx((2.0, 0.0, 0.0))
        assert second_world == pytest.approx((3.2, 0.0, 0.0))

        if not renderer._ensure_context():
            pytest.skip("ModernGL standalone context is unavailable")
        static = renderer.render(model, camera, 128, 128, textures={}, anim_pose=None)
        static_mesh = renderer._mesh_cache.get(id(mesh))
        assert static is not None
        assert static_mesh is not None
        assert static_mesh.scene_rigid_gpu_pose is False

        transform_calls.clear()
        first = renderer.render(model, camera, 128, 128, textures={}, anim_pose=first_pose)
        first_mesh = renderer._mesh_cache.get(id(mesh))
        assert first is not None
        assert first_mesh is not None
        assert first_mesh is not static_mesh
        assert first_mesh.scene_rigid_gpu_pose is True
        assert transform_calls.count(mesh) == 1
        first_vbo = first_mesh.vbo
        first_pixels = first.tobytes()

        transform_calls.clear()
        second = renderer.render(model, camera, 128, 128, textures={}, anim_pose=second_pose)
        second_mesh = renderer._mesh_cache.get(id(mesh))

        assert second is not None
        assert transform_calls.count(mesh) == 1
        assert second_mesh is first_mesh
        assert second_mesh.vbo is first_vbo
        assert second.tobytes() != first_pixels

        static_again = renderer.render(
            model,
            camera,
            128,
            128,
            textures={},
            anim_pose=None,
        )
        rebuilt_static_mesh = renderer._mesh_cache.get(id(mesh))
        assert static_again is not None
        assert rebuilt_static_mesh is not second_mesh
        assert rebuilt_static_mesh.scene_rigid_gpu_pose is False
    finally:
        renderer.release()


def test_moderngl_scoped_pose_keeps_unrelated_static_nodes_on_persistent_transform_cache(
    monkeypatch,
) -> None:
    import src.adapters.rendering.moderngl_renderer_impl as renderer_impl

    from src.adapters.rendering.moderngl_renderer import ModernGLRenderer
    from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags

    scene = ModelNode(name="scene", flags=int(NodeFlags.HEADER))
    static_mesh = ModelNode(
        name="static_room_piece",
        flags=int(NodeFlags.HEADER) | int(NodeFlags.MESH),
        parent=scene,
        position=(0.0, 0.0, 0.0),
        vertices=[(-1.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 2.0)],
        normals=[(0.0, -1.0, 0.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)],
        faces=[(0, 1, 2)],
        texture="",
    )
    actor = ModelNode(
        name="actor",
        flags=int(NodeFlags.HEADER),
        parent=scene,
        position=(2.0, 0.0, 0.0),
    )
    actor._gr_scene_object_root = True
    actor._gr_scene_gpu_transform = True
    actor._gr_scene_object_id = "actor-cache-proof"
    actor._gr_scene_source_position = (2.0, 0.0, 0.0)
    actor_mesh = ModelNode(
        name="actor_rigid_piece",
        flags=int(NodeFlags.HEADER) | int(NodeFlags.MESH),
        parent=actor,
        vertices=[(-0.4, 0.0, 0.0), (0.4, 0.0, 0.0), (0.0, 0.0, 1.2)],
        normals=[(0.0, -1.0, 0.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)],
        faces=[(0, 1, 2)],
        texture="",
    )
    for node in (actor, actor_mesh):
        node._gr_scene_object_id = "actor-cache-proof"
        node._gr_scene_object_root_ref = actor
    scene.children = [static_mesh, actor]
    actor.children = [actor_mesh]
    model = KotorModel(name="scoped-static-cache-proof", root_node=scene)
    model.classification = "tile"

    pose_node = SimpleNamespace(
        name="actor",
        position=(3.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        scale=1.0,
    )
    actor_pose = SimpleNamespace(
        time=0.0,
        nodes={"actor": pose_node},
        nodes_by_index={},
        duplicate_node_names=set(),
        _gr_animation_scene_object_id="actor-cache-proof",
    )

    camera = SimpleNamespace(
        eye=(0.0, -8.0, 2.0),
        target=(1.0, 0.0, 0.8),
        up=(0.0, 0.0, 1.0),
        fov=45.0,
        near=0.01,
        far=100.0,
    )
    renderer = ModernGLRenderer()
    renderer.show_grid = False
    renderer.cull_faces = False
    renderer.enable_frustum_culling = False
    if not renderer._ensure_context():
        pytest.skip("ModernGL standalone context is unavailable")

    animated_calls = []
    static_world_calls = []
    original_animated = renderer_impl._animated_node_world_transform
    original_world = type(static_mesh).world_transform

    def counted_animated(node, pose):
        animated_calls.append(node)
        return original_animated(node, pose)

    def counted_world(node):
        if node is static_mesh:
            static_world_calls.append(node)
        return original_world(node)

    monkeypatch.setattr(
        renderer_impl,
        "_animated_node_world_transform",
        counted_animated,
    )
    monkeypatch.setattr(type(static_mesh), "world_transform", counted_world)
    try:
        first = renderer.render(
            model,
            camera,
            96,
            96,
            textures={},
            anim_pose=ScopedAnimationPoseSet({"actor-cache-proof": actor_pose}),
        )
        assert first is not None
        first_static_world_calls = len(static_world_calls)
        assert first_static_world_calls == 1, (
            renderer.perf,
            [node.name for node in renderer._node_cache_opaque],
            [node.name for node in animated_calls],
            id(static_mesh) in renderer._wt_cache,
        )
        assert static_mesh not in animated_calls
        assert actor_mesh in animated_calls

        animated_calls.clear()
        second = renderer.render(
            model,
            camera,
            96,
            96,
            textures={},
            # Match the viewport contract: the wrapper is new even when the
            # individual actor pose object is unchanged.
            anim_pose=ScopedAnimationPoseSet({"actor-cache-proof": actor_pose}),
        )
        assert second is not None
        assert len(static_world_calls) == first_static_world_calls
        assert static_mesh not in animated_calls
        assert actor_mesh in animated_calls
    finally:
        renderer.release()


def test_moderngl_retained_bas_head_skin_uses_actor_placement_once() -> None:
    """A detachable head skin and its rigid face parts must share one headhook."""

    import numpy as np

    from src.adapters.rendering.moderngl_renderer import ModernGLRenderer
    from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags

    scene = ModelNode(name="scene", flags=int(NodeFlags.HEADER))
    actor = ModelNode(
        name="pie_actor",
        flags=int(NodeFlags.HEADER),
        parent=scene,
        position=(2.0, 0.0, 0.0),
    )
    actor._gr_scene_object_root = True
    actor._gr_scene_object_root_ref = actor
    actor._gr_scene_gpu_transform = True
    actor._gr_scene_object_id = "actor-head-proof"
    actor._gr_map_studio_pie_actor = True
    actor._gr_runtime_source_model_ref = SimpleNamespace(
        bb_min=(-0.8, -0.2, 0.0),
        bb_max=(0.8, 0.2, 2.4),
    )
    body_root = ModelNode(name="pmbam", flags=int(NodeFlags.HEADER), parent=actor)
    headhook = ModelNode(
        name="headhook",
        flags=int(NodeFlags.HEADER),
        parent=body_root,
        position=(0.0, 0.0, 1.5),
    )
    body = ModelNode(
        name="body_rigid",
        flags=int(NodeFlags.HEADER) | int(NodeFlags.MESH),
        parent=body_root,
        vertices=[(-0.65, 0.0, 0.0), (0.65, 0.0, 0.0), (0.0, 0.0, 1.25)],
        normals=[(0.0, -1.0, 0.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)],
        faces=[(0, 1, 2)],
        diffuse=(0.0, 0.0, 1.0),
    )
    head_root = ModelNode(
        name="head_attach",
        flags=int(NodeFlags.HEADER),
        parent=headhook,
    )
    head_root._gr_bas_attachment_layer = True
    head_root._gr_bas_attachment_root = True
    head_root._gr_bas_attachment_root_ref = head_root
    head_root._gr_bas_attachment_slot = "head"
    head_root._gr_bas_socket_name = "headhook"
    head_skin = ModelNode(
        name="head_skin",
        flags=int(NodeFlags.HEADER) | int(NodeFlags.MESH) | int(NodeFlags.SKIN),
        parent=head_root,
        vertices=[(-0.45, 0.0, 0.0), (0.45, 0.0, 0.0), (0.0, 0.0, 0.8)],
        normals=[(0.0, -1.0, 0.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)],
        faces=[(0, 1, 2)],
        diffuse=(0.0, 1.0, 0.0),
    )
    eye = ModelNode(
        name="eye_rigid",
        flags=int(NodeFlags.HEADER) | int(NodeFlags.MESH),
        parent=head_root,
        position=(0.0, -0.02, 0.25),
        vertices=[(-0.16, 0.0, 0.0), (0.16, 0.0, 0.0), (0.0, 0.0, 0.24)],
        normals=[(0.0, -1.0, 0.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)],
        faces=[(0, 1, 2)],
        diffuse=(1.0, 0.0, 0.0),
    )
    for node in (head_skin, eye):
        node._gr_bas_attachment_layer = True
        node._gr_bas_attachment_root_ref = head_root
    scene.children = [actor]
    actor.children = [body_root]
    body_root.children = [body, headhook]
    headhook.children = [head_root]
    head_root.children = [head_skin, eye]
    for node in (body_root, headhook, body, head_root, head_skin, eye):
        node._gr_scene_object_id = "actor-head-proof"
        node._gr_scene_object_root_ref = actor

    model = KotorModel(name="retained-bas-head-proof", root_node=scene)
    model.classification = "character"
    pose_nodes = {
        node.name.lower(): SimpleNamespace(
            name=node.name,
            position=node.position,
            rotation=node.rotation,
            scale=1.0,
        )
        for node in (body_root, headhook, body, head_root, head_skin, eye)
    }
    pose = SimpleNamespace(
        time=0.5,
        nodes=pose_nodes,
        nodes_by_index={},
        duplicate_node_names=set(),
        _gr_animation_scene_object_id="actor-head-proof",
    )
    scoped_pose = ScopedAnimationPoseSet({"actor-head-proof": pose})
    camera = SimpleNamespace(
        eye=(2.0, -8.0, 2.0),
        target=(2.0, 0.0, 1.2),
        up=(0.0, 0.0, 1.0),
        fov=45.0,
        near=0.01,
        far=100.0,
    )
    renderer = ModernGLRenderer()
    renderer.show_grid = False
    renderer.cull_faces = False
    renderer.lighting_mode = "fullbright"

    def colored_centroid(image, channel: int) -> tuple[int, float]:
        pixels = np.asarray(image.convert("RGB"), dtype=np.float32)
        selected = pixels[:, :, channel] > 140.0
        for other in range(3):
            if other != channel:
                selected &= pixels[:, :, channel] > (pixels[:, :, other] * 1.5)
        ys, xs = np.nonzero(selected)
        return int(len(xs)), float(np.mean(xs)) if len(xs) else float("nan")

    try:
        if not renderer._ensure_context():
            pytest.skip("ModernGL standalone context is unavailable")
        culling_on = renderer.render(
            model,
            camera,
            512,
            512,
            textures={},
            anim_pose=scoped_pose,
        )
        assert culling_on is not None
        assert renderer.perf["draw_calls"] == 3
        assert renderer.perf["culled_actor_meshes"] == 0
        head_count, head_x = colored_centroid(culling_on, 1)
        eye_count, eye_x = colored_centroid(culling_on, 0)
        body_count, body_x = colored_centroid(culling_on, 2)
        assert min(head_count, eye_count, body_count) > 0
        assert abs(head_x - eye_x) < 5.0
        assert abs(head_x - body_x) < 5.0

        renderer.enable_frustum_culling = False
        culling_off = renderer.render(
            model,
            camera,
            512,
            512,
            textures={},
            anim_pose=scoped_pose,
        )
        assert culling_off is not None
        assert renderer.perf["draw_calls"] == 3
        assert culling_off.tobytes() == culling_on.tobytes()
    finally:
        renderer.release()


def test_moderngl_bas_duplicate_bind_name_keeps_body_skin_on_support_plane() -> None:
    """A head attachment's zeroed rootdummy must not sink the primary body skin."""

    import numpy as np

    from src.adapters.rendering.moderngl_renderer import ModernGLRenderer
    from src.core.animation.animation_engine import AnimationEngine
    from src.core.geometry.model_data import (
        Animation,
        BoneWeight,
        KotorModel,
        ModelNode,
        NodeFlags,
        VertexSkinData,
    )

    body_root = ModelNode(name="body")
    body_rootdummy = ModelNode(
        name="rootdummy",
        position=(0.0, 0.0, 1.12557),
        parent=body_root,
    )
    body_skin = ModelNode(
        name="torso",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN),
        parent=body_root,
        vertices=[(-0.5, 0.0, 0.0), (0.5, 0.0, 0.0), (0.0, 0.0, 1.0)],
        normals=[(0.0, -1.0, 0.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)],
        faces=[(0, 1, 2)],
        diffuse=(0.0, 1.0, 0.0),
    )
    body_skin.bone_map = ["rootdummy"]
    body_skin.skin_data = [
        VertexSkinData([BoneWeight(0, 1.0)])
        for _ in body_skin.vertices
    ]
    headhook = ModelNode(name="headhook", parent=body_rootdummy)
    attachment_root = ModelNode(name="head_attachment", parent=headhook)
    attachment_root._gr_bas_attachment_layer = True
    attachment_root._gr_bas_attachment_root = True
    attachment_rootdummy = ModelNode(
        name="rootdummy",
        position=(0.0, 0.0, 0.0),
        parent=attachment_root,
    )
    attachment_rootdummy._gr_bas_attachment_layer = True
    body_root.children = [body_rootdummy, body_skin]
    body_rootdummy.children = [headhook]
    headhook.children = [attachment_root]
    attachment_root.children = [attachment_rootdummy]

    animation_rootdummy = ModelNode(
        name="rootdummy",
        controllers=[
            {
                "type": 8,
                "name": "position",
                "columns": 3,
                "times": [0.0],
                "values": [[0.0, 0.0, -0.00665]],
            }
        ],
    )
    model = KotorModel(
        name="body_with_detachable_head",
        root_node=body_root,
        animations=[Animation(name="pause1", length=1.0, nodes=[animation_rootdummy])],
    )
    engine = AnimationEngine(model)
    assert engine.play("pause1", loop=True, blend=False)
    pose = engine.evaluate(0.0)
    assert pose.nodes["rootdummy"].position[2] == pytest.approx(1.11892)

    camera = SimpleNamespace(
        eye=(0.0, -5.0, 0.5),
        target=(0.0, 0.0, 0.5),
        up=(0.0, 0.0, 1.0),
        fov=45.0,
        near=0.01,
        far=100.0,
    )
    renderer = ModernGLRenderer()
    renderer.show_grid = False
    renderer.cull_faces = False
    renderer.lighting_mode = "fullbright"
    try:
        if not renderer._ensure_context():
            pytest.skip("ModernGL standalone context is unavailable")
        image = renderer.render(model, camera, 256, 256, textures={}, anim_pose=pose)
        assert image is not None
        assert renderer.perf["draw_calls"] == 1

        # Decode the exact column-major palette bytes uploaded to u_bones.  The
        # animation is a 6.65 mm root delta; the detachable head must not turn
        # it into a -1.132 m body translation by replacing the 1.12557 m bind.
        cached = next(iter(renderer._skin_palette_bytes_cache.values()))
        palette = np.frombuffer(cached[2], dtype=np.float32).reshape(-1, 4, 4)
        palette = palette.transpose((0, 2, 1))
        assert palette[0, 2, 3] == pytest.approx(-0.00665, abs=1.0e-5)

        pixels = np.asarray(image.convert("RGB"), dtype=np.float32)
        green = pixels[:, :, 1] > 80.0
        green &= pixels[:, :, 1] > pixels[:, :, 0] * 1.5
        green &= pixels[:, :, 1] > pixels[:, :, 2] * 1.5
        ys, _xs = np.nonzero(green)
        assert len(ys) > 100
        assert int(ys.min()) < 110
        assert int(ys.max()) < 180
    finally:
        renderer.release()


def test_moderngl_skin_palette_cache_is_actor_local_and_pose_stamped() -> None:
    from src.adapters.rendering.moderngl_renderer import ModernGLRenderer

    class FakeUploader:
        def __init__(self, marker: bytes):
            self.marker = marker
            self.compute_calls = 0
            self._skin_palette_formula = ""
            self._skin_inverse_bind_source = ""

        def compute_skin_node_palette(self, skin_node, anim_pose, *, anim_base_pose=None):
            self.compute_calls += 1
            self._skin_palette_formula = f"formula-{self.marker.decode()}"
            self._skin_inverse_bind_source = f"bind-{self.marker.decode()}"

        def as_flat_bytes(self):
            return self.marker * 16

    renderer = ModernGLRenderer()
    skin_a = SimpleNamespace(bone_map=["root"])
    skin_b = SimpleNamespace(bone_map=["root"])
    uploader_a = FakeUploader(b"A")
    uploader_b = FakeUploader(b"B")
    pose_a = SimpleNamespace(time=1.0, nodes={"root": object()})
    pose_b = SimpleNamespace(time=1.0, nodes={"root": object()})
    signature = ("skin", 1)

    count_a, bytes_a, cached_a = renderer._skin_palette_bytes_for_draw(
        scope_key=("runtime_actor", "actor-a"),
        skin_node=skin_a,
        uploader=uploader_a,
        anim_pose=pose_a,
        anim_base_pose=None,
        skin_signature=signature,
    )
    count_b, bytes_b, cached_b = renderer._skin_palette_bytes_for_draw(
        scope_key=("runtime_actor", "actor-b"),
        skin_node=skin_b,
        uploader=uploader_b,
        anim_pose=pose_b,
        anim_base_pose=None,
        skin_signature=signature,
    )
    repeat_count_a, repeat_bytes_a, repeat_cached_a = renderer._skin_palette_bytes_for_draw(
        scope_key=("runtime_actor", "actor-a"),
        skin_node=skin_a,
        uploader=uploader_a,
        anim_pose=pose_a,
        anim_base_pose=None,
        skin_signature=signature,
    )

    assert (count_a, count_b, repeat_count_a) == (1, 1, 1)
    assert cached_a is False
    assert cached_b is False
    assert repeat_cached_a is True
    assert bytes_a == repeat_bytes_a
    assert bytes_a != bytes_b
    assert uploader_a.compute_calls == 1
    assert uploader_b.compute_calls == 1

    moved_pose_a = SimpleNamespace(time=1.25, nodes={"root": object()})
    _count, moved_bytes_a, moved_cached_a = renderer._skin_palette_bytes_for_draw(
        scope_key=("runtime_actor", "actor-a"),
        skin_node=skin_a,
        uploader=uploader_a,
        anim_pose=moved_pose_a,
        anim_base_pose=None,
        skin_signature=signature,
    )
    _count, repeat_bytes_b, repeat_cached_b = renderer._skin_palette_bytes_for_draw(
        scope_key=("runtime_actor", "actor-b"),
        skin_node=skin_b,
        uploader=uploader_b,
        anim_pose=pose_b,
        anim_base_pose=None,
        skin_signature=signature,
    )

    assert moved_cached_a is False
    assert repeat_cached_b is True
    assert moved_bytes_a == bytes_a
    assert repeat_bytes_b == bytes_b
    assert uploader_a.compute_calls == 2
    assert uploader_b.compute_calls == 1


def test_moderngl_bas_head_palette_is_converted_to_attachment_root_local_space() -> None:
    import numpy as np

    from src.adapters.rendering.moderngl_renderer import ModernGLRenderer
    from src.core.animation.gpu_skinning import MAX_BONES

    root = SimpleNamespace(
        name="head_root",
        parent=None,
        children=[],
        position=(0.0, 0.0, 10.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        _gr_bas_attachment_layer=True,
        _gr_bas_attachment_root=True,
        _gr_bas_attachment_slot="head",
    )
    skin = SimpleNamespace(
        name="head_skin",
        parent=root,
        children=[],
        bone_map=["jaw"],
        _gr_bas_attachment_layer=True,
        _gr_bas_attachment_root_ref=root,
    )
    root.children = [skin]

    class FakeUploader:
        _skin_palette_formula = "pose_world_times_inverse_bind"
        _skin_inverse_bind_source = "bind"

        def compute_skin_node_palette(self, *_args, **_kwargs):
            return None

        def as_numpy_array(self):
            palette = np.asarray([np.eye(4, dtype=np.float32)], dtype=np.float32)
            palette[0, 2, 3] = 12.0
            return palette

    renderer = ModernGLRenderer()
    count, raw, cached = renderer._skin_palette_bytes_for_draw(
        scope_key=("bas_attachment", id(root)),
        skin_node=skin,
        uploader=FakeUploader(),
        anim_pose=SimpleNamespace(time=0.0, nodes={}),
        anim_base_pose=None,
        skin_signature=("head_skin", 1),
    )
    matrices = np.frombuffer(raw, dtype=np.float32).reshape(MAX_BONES, 4, 4).transpose((0, 2, 1))
    assert count == 1
    assert cached is False
    assert matrices[0, 2, 3] == pytest.approx(2.0)

def test_moderngl_transformed_bounds_culling_is_conservative() -> None:
    import numpy as np

    from src.adapters.rendering.moderngl_renderer import ModernGLRenderer

    unit_cube_planes = (
        (1.0, 0.0, 0.0, 1.0),
        (-1.0, 0.0, 0.0, 1.0),
        (0.0, 1.0, 0.0, 1.0),
        (0.0, -1.0, 0.0, 1.0),
        (0.0, 0.0, 1.0, 1.0),
        (0.0, 0.0, -1.0, 1.0),
    )
    bounds = ((10.0, 10.0, 10.0), (11.0, 11.0, 11.0))
    identity = np.eye(4, dtype=np.float32)
    translated = np.eye(4, dtype=np.float32)
    translated[:3, 3] = (-10.5, -10.5, -10.5)

    assert ModernGLRenderer._transformed_bounds_outside_frustum(
        bounds, identity, unit_cube_planes
    ) is True
    assert ModernGLRenderer._transformed_bounds_outside_frustum(
        bounds, translated, unit_cube_planes
    ) is False
    assert ModernGLRenderer._transformed_bounds_outside_frustum(
        None, identity, unit_cube_planes
    ) is False


def test_moderngl_pie_actor_frustum_culls_whole_transparent_actor() -> None:
    from src.adapters.rendering.moderngl_renderer import ModernGLRenderer
    from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags

    scene = ModelNode(name="scene", flags=int(NodeFlags.HEADER))
    actor = ModelNode(
        name="offscreen_actor",
        flags=int(NodeFlags.HEADER),
        parent=scene,
        position=(80.0, 0.0, 0.0),
    )
    actor._gr_scene_object_root = True
    actor._gr_scene_gpu_transform = True
    actor._gr_scene_object_id = "actor-offscreen"
    actor._gr_map_studio_pie_actor = True
    actor._gr_runtime_source_model_ref = SimpleNamespace(
        bb_min=(-0.5, -0.5, 0.0),
        bb_max=(0.5, 0.5, 1.8),
    )
    mesh = ModelNode(
        name="transparent_actor_mesh",
        flags=int(NodeFlags.HEADER) | int(NodeFlags.MESH),
        parent=actor,
        vertices=[(-0.5, 0.0, 0.0), (0.5, 0.0, 0.0), (0.0, 0.0, 1.0)],
        normals=[(0.0, -1.0, 0.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)],
        faces=[(0, 1, 2)],
        texture="",
    )
    mesh.alpha = 0.5
    mesh._gr_scene_object_id = "actor-offscreen"
    mesh._gr_scene_object_root_ref = actor
    actor._gr_scene_object_root_ref = actor
    actor.children = [mesh]
    scene.children = [actor]
    model = KotorModel(name="pie-actor-frustum-proof", root_node=scene)
    model.classification = "character"
    camera = SimpleNamespace(
        eye=(0.0, -6.0, 2.0),
        target=(0.0, 0.0, 0.5),
        up=(0.0, 0.0, 1.0),
        fov=45.0,
        near=0.01,
        far=100.0,
    )
    renderer = ModernGLRenderer()
    renderer.show_grid = False
    renderer.cull_faces = False
    renderer.selected_node = mesh
    try:
        if not renderer._ensure_context():
            pytest.skip("ModernGL standalone context is unavailable")
        image = renderer.render(model, camera, 128, 128, textures={})
        assert image is not None
        culled_pixels = image.tobytes()
        assert renderer.perf["culled_actor_meshes"] == 1
        assert renderer.perf["culled_meshes"] == 1
        assert renderer.perf["draw_calls"] == 0
        # Rendering culls only submission; selection/picking scene state is intact.
        assert renderer.selected_node is mesh
        assert mesh in model.all_nodes()

        renderer.enable_frustum_culling = False
        uncull_image = renderer.render(model, camera, 128, 128, textures={})
        assert uncull_image is not None
        assert renderer.perf["draw_calls"] == 1
        # Submitting the offscreen transparent mesh changes no visible pixels.
        assert uncull_image.tobytes() == culled_pixels

        actor.position = (0.0, 0.0, 0.0)
        renderer.enable_frustum_culling = True
        image = renderer.render(model, camera, 128, 128, textures={})
        assert image is not None
        assert renderer.perf["culled_actor_meshes"] == 0
        assert renderer.perf["draw_calls"] == 1
    finally:
        renderer.release()


def test_moderngl_rigid_pie_door_uses_tight_mesh_frustum_bounds() -> None:
    from src.adapters.rendering.moderngl_renderer import ModernGLRenderer
    from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags

    scene = ModelNode(name="scene", flags=int(NodeFlags.HEADER))
    actor = ModelNode(
        name="offscreen_door",
        flags=int(NodeFlags.HEADER),
        parent=scene,
        position=(80.0, 0.0, 0.0),
    )
    actor._gr_scene_object_root = True
    actor._gr_scene_gpu_transform = True
    actor._gr_scene_object_id = "door-offscreen"
    actor._gr_map_studio_pie_actor = True
    actor._gr_map_studio_pie_rigid_actor = True
    # A deliberately loose stock door header intersects the camera frustum,
    # while the actual panel mesh is far outside it.
    actor._gr_runtime_source_model_ref = SimpleNamespace(
        bb_min=(-100.0, -100.0, -100.0),
        bb_max=(100.0, 100.0, 100.0),
    )
    mesh = ModelNode(
        name="door_panel",
        flags=int(NodeFlags.HEADER) | int(NodeFlags.MESH),
        parent=actor,
        vertices=[(-0.5, 0.0, 0.0), (0.5, 0.0, 0.0), (0.0, 0.0, 2.0)],
        normals=[(0.0, -1.0, 0.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)],
        faces=[(0, 1, 2)],
        texture="",
    )
    mesh._gr_scene_object_id = "door-offscreen"
    mesh._gr_scene_object_root_ref = actor
    actor._gr_scene_object_root_ref = actor
    actor.children = [mesh]
    scene.children = [actor]
    model = KotorModel(name="pie-rigid-door-frustum-proof", root_node=scene)
    model.classification = "character"
    camera = SimpleNamespace(
        eye=(0.0, -6.0, 2.0),
        target=(0.0, 0.0, 0.5),
        up=(0.0, 0.0, 1.0),
        fov=45.0,
        near=0.01,
        far=100.0,
    )
    renderer = ModernGLRenderer()
    renderer.show_grid = False
    renderer.cull_faces = False
    try:
        if not renderer._ensure_context():
            pytest.skip("ModernGL standalone context is unavailable")
        image = renderer.render(model, camera, 128, 128, textures={})
        assert image is not None
        assert renderer.perf["culled_actor_meshes"] == 0
        assert renderer.perf["culled_meshes"] == 1
        assert renderer.perf["draw_calls"] == 0
    finally:
        renderer.release()


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
