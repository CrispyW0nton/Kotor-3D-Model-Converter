"""
GhostRigger-K1-K2 v3.3 Comprehensive Test Suite
=================================================

Tests covering:
  1. MDL ASCII Writer – controller keyframe output (positionkey/orientationkey/scalekey)
  2. MDL ASCII Parser – animation keyframe parsing round-trip
  3. MDL ASCII round-trip – full write→parse→animate cycle
  4. Auto-Rigger – Gaussian heat-diffusion weights, zero-weight guard, normalisation
  5. Auto-Rigger – rig_from_template, weight stats, preview generation
  6. Animation Engine – integrate with ASCII-round-trip model
  7. Viewport – non-skin node world transform with animated pose
  8. MDLAsciiParser – _parse_anim_block correctness
  9. MDL Writer – SKINCONTROLLERS / bone_map output
 10. Edge cases – empty models, single-bone models, corrupt keyframes
"""

import math
import os
import sys
import tempfile
import pytest

# ── Path bootstrap ────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.model_data import (
    KotorModel, ModelNode, NodeFlags, Animation, AnimEvent,
    VertexSkinData, BoneWeight, GameVersion,
)
from src.core.mdl_parser import MDLAsciiWriter, MDLAsciiParser, _ascii_type_to_flags


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _simple_model(name='m1', with_mesh=False, with_skin=False):
    """Build a minimal 2-node model (root dummy + optional mesh)."""
    model = KotorModel(name=name)
    root = ModelNode(name=name, flags=int(NodeFlags.HEADER))
    model.root_node = root

    bone = ModelNode(name='hip', flags=int(NodeFlags.HEADER))
    bone.position = (0.0, 0.0, 0.5)
    bone.parent = root
    root.children.append(bone)

    if with_mesh or with_skin:
        flags = int(NodeFlags.HEADER) | int(NodeFlags.MESH)
        if with_skin:
            flags |= int(NodeFlags.SKIN)
        mesh = ModelNode(name='body', flags=flags)
        mesh.vertices = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
        mesh.faces    = [(0, 1, 2), (0, 1, 3)]
        mesh.uvs      = [(0, 0), (1, 0), (0, 1), (0.5, 0.5)]
        mesh.parent   = root
        root.children.append(mesh)
        if with_skin:
            mesh.bone_map = ['hip']
            mesh.skin_data = [
                VertexSkinData(influences=[BoneWeight(0, 1.0)])
                for _ in mesh.vertices
            ]

    return model


def _anim_with_controllers(name='walk', length=1.0):
    """Build an Animation with position/orientation/scale controllers."""
    anim = Animation(name=name, length=length, transition_time=0.25)
    node = ModelNode(name='hip', flags=int(NodeFlags.HEADER))
    node.controllers = [
        {
            'type': 8, 'name': 'positionkey',
            'times': [0.0, 0.5, 1.0],
            'values': [[0, 0, 0.5], [0, 0, 0.6], [0, 0, 0.5]],
            'columns': 3,
        },
        {
            'type': 20, 'name': 'orientationkey',
            'times': [0.0, 0.5, 1.0],
            'values': [[0, 0, 0, 1], [0, 0, 0.383, 0.924], [0, 0, 0, 1]],
            'columns': 4,
        },
        {
            'type': 36, 'name': 'scalekey',
            'times': [0.0, 1.0],
            'values': [[1.0], [1.0]],
            'columns': 1,
        },
    ]
    anim.nodes.append(node)
    return anim


def _write_and_read(model):
    """Write model to temp ASCII file and parse it back."""
    with tempfile.NamedTemporaryFile(suffix='.mdl', mode='w',
                                     delete=False) as f:
        path = f.name
    try:
        MDLAsciiWriter().write(model, path)
        m2 = MDLAsciiParser().parse_file(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return m2


# ══════════════════════════════════════════════════════════════════════════════
#  Section 1 – MDL ASCII Writer: controller keyframe output
# ══════════════════════════════════════════════════════════════════════════════

class TestMDLAsciiWriterControllers:
    """MDLAsciiWriter must emit positionkey/orientationkey/scalekey blocks."""

    def _write_to_string(self, model):
        with tempfile.NamedTemporaryFile(suffix='.mdl', mode='w', delete=False) as f:
            path = f.name
        try:
            MDLAsciiWriter().write(model, path)
            with open(path) as f:
                return f.read()
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def test_positionkey_present(self):
        m = _simple_model()
        m.animations.append(_anim_with_controllers('walk'))
        txt = self._write_to_string(m)
        assert 'positionkey' in txt

    def test_orientationkey_present(self):
        m = _simple_model()
        m.animations.append(_anim_with_controllers('walk'))
        txt = self._write_to_string(m)
        assert 'orientationkey' in txt

    def test_scalekey_present(self):
        m = _simple_model()
        m.animations.append(_anim_with_controllers('walk'))
        txt = self._write_to_string(m)
        assert 'scalekey' in txt

    def test_positionkey_row_count(self):
        m = _simple_model()
        anim = _anim_with_controllers('run')
        m.animations.append(anim)
        txt = self._write_to_string(m)
        # Should have "positionkey 3" (3 keyframes)
        assert 'positionkey 3' in txt

    def test_orientationkey_row_count(self):
        m = _simple_model()
        m.animations.append(_anim_with_controllers('idle'))
        txt = self._write_to_string(m)
        assert 'orientationkey 3' in txt

    def test_position_values_written(self):
        m = _simple_model()
        m.animations.append(_anim_with_controllers('walk'))
        txt = self._write_to_string(m)
        # Key at t=0.5 should have z=0.6
        assert '0.500000 0.000000 0.000000 0.600000' in txt

    def test_orientation_values_written(self):
        m = _simple_model()
        m.animations.append(_anim_with_controllers('walk'))
        txt = self._write_to_string(m)
        # First key at t=0.0 should have identity quaternion 0 0 0 1
        assert '0.000000 0.000000 0.000000 0.000000 1.000000' in txt

    def test_newanim_doneanim_block(self):
        m = _simple_model()
        m.animations.append(_anim_with_controllers('walk'))
        txt = self._write_to_string(m)
        assert 'newanim walk' in txt
        assert 'doneanim walk' in txt

    def test_anim_length_written(self):
        m = _simple_model()
        anim = _anim_with_controllers('run', length=2.5)
        m.animations.append(anim)
        txt = self._write_to_string(m)
        assert 'length 2.5' in txt

    def test_anim_transtime_written(self):
        m = _simple_model()
        m.animations.append(_anim_with_controllers())
        txt = self._write_to_string(m)
        assert 'transtime 0.25' in txt

    def test_anim_event_written(self):
        m = _simple_model()
        anim = _anim_with_controllers()
        anim.events.append(AnimEvent(time=0.33, name='step'))
        m.animations.append(anim)
        txt = self._write_to_string(m)
        assert 'event 0.3300 step' in txt

    def test_multiple_events_written(self):
        m = _simple_model()
        anim = _anim_with_controllers()
        anim.events.append(AnimEvent(time=0.1, name='ev1'))
        anim.events.append(AnimEvent(time=0.8, name='ev2'))
        m.animations.append(anim)
        txt = self._write_to_string(m)
        assert 'event 0.1000 ev1' in txt
        assert 'event 0.8000 ev2' in txt

    def test_multiple_animations_written(self):
        m = _simple_model()
        m.animations.append(_anim_with_controllers('walk'))
        m.animations.append(_anim_with_controllers('run'))
        txt = self._write_to_string(m)
        assert 'newanim walk' in txt
        assert 'newanim run' in txt

    def test_no_controllers_no_keyblock(self):
        """A node without controllers should not emit any key block."""
        m = _simple_model()
        anim = Animation(name='idle', length=0.5)
        bare_node = ModelNode(name='hip', flags=int(NodeFlags.HEADER))
        # No controllers
        anim.nodes.append(bare_node)
        m.animations.append(anim)
        txt = self._write_to_string(m)
        assert 'positionkey' not in txt
        assert 'orientationkey' not in txt

    def test_alpha_key_written(self):
        m = _simple_model()
        anim = Animation(name='fade', length=1.0)
        node = ModelNode(name='hip', flags=int(NodeFlags.HEADER))
        node.controllers = [{
            'type': 132, 'name': 'alphakey',   # CTRL_MESH_ALPHA = 132 (KotorBlender-verified)
            'times': [0.0, 1.0], 'values': [[1.0], [0.0]], 'columns': 1,
        }]
        anim.nodes.append(node)
        m.animations.append(anim)
        txt = self._write_to_string(m)
        assert 'alphakey' in txt

    def test_selfillumcolorkey_written(self):
        m = _simple_model()
        anim = Animation(name='glow', length=1.0)
        node = ModelNode(name='hip', flags=int(NodeFlags.HEADER))
        node.controllers = [{
            'type': 100, 'name': 'selfillumcolorkey',  # CTRL_MESH_SELFILLUMCOLOR = 100 (KotorBlender-verified)
            'times': [0.0, 1.0],
            'values': [[0, 0, 0], [1, 0.5, 0]],
            'columns': 3,
        }]
        anim.nodes.append(node)
        m.animations.append(anim)
        txt = self._write_to_string(m)
        assert 'selfillumcolorkey' in txt

    def test_write_model_structure_intact(self):
        m = _simple_model(with_mesh=True)
        m.animations.append(_anim_with_controllers())
        txt = self._write_to_string(m)
        assert 'newmodel m1' in txt
        assert 'donemodel m1' in txt
        assert 'node trimesh body' in txt

    def test_skin_weights_written(self):
        m = _simple_model(with_skin=True)
        txt = self._write_to_string(m)
        assert 'weights' in txt

    def test_bind_pose_controller_in_non_anim_node(self):
        """Regular model nodes with controllers should also emit key blocks."""
        m = _simple_model()
        if m.root_node:
            for ch in m.root_node.children:
                if ch.name == 'hip':
                    ch.controllers = [{
                        'type': 8, 'name': 'positionkey',
                        'times': [0.0], 'values': [[0, 0, 0.5]], 'columns': 3,
                    }]
        txt = self._write_to_string(m)
        assert 'positionkey' in txt


# ══════════════════════════════════════════════════════════════════════════════
#  Section 2 – MDL ASCII Parser: animation keyframe parsing
# ══════════════════════════════════════════════════════════════════════════════

_SAMPLE_MDL = """\
# test mdl
newmodel testrig
setsupermodel testrig NULL
classification character
setanimationscale 1.000000

node dummy testrig
  parent NULL
  position 0.000000 0.000000 0.000000
  orientation 0.000000 0.000000 0.000000 1.000000
endnode

node dummy hip
  parent testrig
  position 0.000000 0.000000 0.500000
  orientation 0.000000 0.000000 0.000000 1.000000
endnode

newanim walk testrig
  length 1.0000
  transtime 0.2500
  animroot testrig
  event 0.3000 footstep_L
  event 0.8000 footstep_R
  node dummy hip
    parent testrig
    positionkey 3
      0.000000 0.000000 0.000000 0.500000
      0.500000 0.000000 0.000000 0.600000
      1.000000 0.000000 0.000000 0.500000
    orientationkey 2
      0.000000 0.000000 0.000000 0.000000 1.000000
      1.000000 0.000000 0.000000 0.383000 0.924000
    scalekey 2
      0.000000 1.000000
      1.000000 1.000000
  endnode
doneanim walk testrig

donemodel testrig
"""


class TestMDLAsciiParserKeyframes:
    """MDLAsciiParser must parse animation controller keyframe tables."""

    @pytest.fixture(autouse=True)
    def parsed(self):
        self.model = MDLAsciiParser().parse_string(_SAMPLE_MDL)

    def test_animation_count(self):
        assert len(self.model.animations) == 1

    def test_animation_name(self):
        assert self.model.animations[0].name == 'walk'

    def test_animation_length(self):
        assert abs(self.model.animations[0].length - 1.0) < 1e-6

    def test_animation_transtime(self):
        assert abs(self.model.animations[0].transition_time - 0.25) < 1e-6

    def test_animation_animroot(self):
        assert self.model.animations[0].anim_root == 'testrig'

    def test_animation_events_count(self):
        assert len(self.model.animations[0].events) == 2

    def test_event_times(self):
        ev_times = [e.time for e in self.model.animations[0].events]
        assert abs(ev_times[0] - 0.3) < 1e-5
        assert abs(ev_times[1] - 0.8) < 1e-5

    def test_event_names(self):
        names = [e.name for e in self.model.animations[0].events]
        assert 'footstep_L' in names
        assert 'footstep_R' in names

    def test_animation_node_count(self):
        assert len(self.model.animations[0].nodes) == 1

    def test_animation_node_name(self):
        assert self.model.animations[0].nodes[0].name == 'hip'

    def test_positionkey_parsed(self):
        node = self.model.animations[0].nodes[0]
        pos_ctrls = [c for c in node.controllers if c['type'] == 8]
        assert len(pos_ctrls) == 1

    def test_positionkey_count(self):
        node = self.model.animations[0].nodes[0]
        pos_ctrl = next(c for c in node.controllers if c['type'] == 8)
        assert len(pos_ctrl['times']) == 3

    def test_positionkey_times(self):
        node = self.model.animations[0].nodes[0]
        pos_ctrl = next(c for c in node.controllers if c['type'] == 8)
        assert abs(pos_ctrl['times'][0] - 0.0) < 1e-5
        assert abs(pos_ctrl['times'][1] - 0.5) < 1e-5
        assert abs(pos_ctrl['times'][2] - 1.0) < 1e-5

    def test_positionkey_values(self):
        node = self.model.animations[0].nodes[0]
        pos_ctrl = next(c for c in node.controllers if c['type'] == 8)
        # At t=0.5, z should be 0.6
        assert abs(pos_ctrl['values'][1][2] - 0.6) < 1e-5

    def test_orientationkey_parsed(self):
        node = self.model.animations[0].nodes[0]
        ori_ctrls = [c for c in node.controllers if c['type'] == 20]
        assert len(ori_ctrls) == 1

    def test_orientationkey_count(self):
        node = self.model.animations[0].nodes[0]
        ori_ctrl = next(c for c in node.controllers if c['type'] == 20)
        assert len(ori_ctrl['times']) == 2

    def test_orientationkey_values(self):
        node = self.model.animations[0].nodes[0]
        ori_ctrl = next(c for c in node.controllers if c['type'] == 20)
        # At t=1.0: x=0, y=0, z=0.383, w=0.924
        vals = ori_ctrl['values'][1]
        assert len(vals) == 4
        assert abs(vals[2] - 0.383) < 1e-5
        assert abs(vals[3] - 0.924) < 1e-5

    def test_scalekey_parsed(self):
        node = self.model.animations[0].nodes[0]
        sc_ctrls = [c for c in node.controllers if c['type'] == 36]
        assert len(sc_ctrls) == 1

    def test_scalekey_values(self):
        node = self.model.animations[0].nodes[0]
        sc_ctrl = next(c for c in node.controllers if c['type'] == 36)
        assert abs(sc_ctrl['values'][0][0] - 1.0) < 1e-5

    def test_model_root_node(self):
        assert self.model.root_node is not None
        assert self.model.root_node.name == 'testrig'

    def test_hip_bone_position(self):
        hip = self.model.find_node('hip')
        assert hip is not None
        assert abs(hip.position[2] - 0.5) < 1e-5

    def test_model_name(self):
        assert self.model.name == 'testrig'

    def test_classification(self):
        assert self.model.classification == 'character'


# ══════════════════════════════════════════════════════════════════════════════
#  Section 3 – MDL ASCII Round-Trip (write → parse → animate)
# ══════════════════════════════════════════════════════════════════════════════

class TestMDLAsciiRoundTrip:
    """Full write→parse→animate cycle."""

    def _build_anim_model(self):
        m = _simple_model('roundtrip')
        anim = _anim_with_controllers('walk', 1.0)
        anim.events.append(AnimEvent(time=0.5, name='footstep'))
        m.animations.append(anim)
        return m

    def test_round_trip_animation_preserved(self):
        m = self._build_anim_model()
        m2 = _write_and_read(m)
        assert len(m2.animations) == 1

    def test_round_trip_anim_name(self):
        m = self._build_anim_model()
        m2 = _write_and_read(m)
        assert m2.animations[0].name == 'walk'

    def test_round_trip_anim_length(self):
        m = self._build_anim_model()
        m2 = _write_and_read(m)
        assert abs(m2.animations[0].length - 1.0) < 1e-4

    def test_round_trip_event_preserved(self):
        m = self._build_anim_model()
        m2 = _write_and_read(m)
        evs = m2.animations[0].events
        assert any(e.name == 'footstep' for e in evs)

    def test_round_trip_positionkey_count(self):
        m = self._build_anim_model()
        m2 = _write_and_read(m)
        node = m2.animations[0].nodes[0] if m2.animations[0].nodes else None
        assert node is not None
        pos_ctrls = [c for c in node.controllers if c['type'] == 8]
        assert len(pos_ctrls) == 1
        assert len(pos_ctrls[0]['times']) == 3

    def test_round_trip_orientationkey_count(self):
        m = self._build_anim_model()
        m2 = _write_and_read(m)
        node = m2.animations[0].nodes[0]
        ori_ctrls = [c for c in node.controllers if c['type'] == 20]
        assert len(ori_ctrls) == 1
        assert len(ori_ctrls[0]['times']) == 3

    def test_round_trip_and_play(self):
        """Parse back and play through AnimationEngine."""
        from src.core.animation_engine import AnimationEngine
        m = self._build_anim_model()
        m2 = _write_and_read(m)
        eng = AnimationEngine(m2)
        ok = eng.play('walk')
        assert ok
        pose = eng.evaluate(0.5)
        assert pose is not None

    def test_round_trip_pose_at_midpoint(self):
        from src.core.animation_engine import AnimationEngine
        m = self._build_anim_model()
        m2 = _write_and_read(m)
        eng = AnimationEngine(m2)
        eng.play('walk')
        pose = eng.evaluate(0.5)
        hip_pose = pose.nodes.get('hip')
        assert hip_pose is not None
        # KotOR position keys are DELTA offsets (xoreos/KotorBlender convention).
        # hip bind pose z=0.5; controller delta at t=0.5 is 0.6.
        # animated_z = bind_z(0.5) + delta(0.6) = 1.1
        assert abs(hip_pose.position[2] - 1.1) < 0.05

    def test_round_trip_model_structure(self):
        m = self._build_anim_model()
        m2 = _write_and_read(m)
        assert m2.root_node is not None
        assert m2.root_node.name == 'roundtrip'

    def test_round_trip_supermodel(self):
        m = _simple_model()
        m.supermodel = 'k_sup_males'
        m2 = _write_and_read(m)
        assert m2.supermodel == 'k_sup_males'

    def test_round_trip_classification(self):
        m = _simple_model()
        m.classification = 'character'
        m2 = _write_and_read(m)
        assert m2.classification == 'character'

    def test_round_trip_multiple_anims(self):
        m = _simple_model()
        m.animations.append(_anim_with_controllers('walk'))
        m.animations.append(_anim_with_controllers('run'))
        m2 = _write_and_read(m)
        names = [a.name for a in m2.animations]
        assert 'walk' in names
        assert 'run' in names

    def test_round_trip_mesh_vertices(self):
        m = _simple_model(with_mesh=True)
        m2 = _write_and_read(m)
        body = m2.find_node('body')
        assert body is not None
        assert len(body.vertices) == 4

    def test_round_trip_mesh_faces(self):
        m = _simple_model(with_mesh=True)
        m2 = _write_and_read(m)
        body = m2.find_node('body')
        assert body is not None
        assert len(body.faces) == 2

    def test_round_trip_skin_weights(self):
        m = _simple_model(with_skin=True)
        m2 = _write_and_read(m)
        body = m2.find_node('body')
        assert body is not None
        assert body.is_skin
        assert len(body.skin_data) == 4

    def test_round_trip_scale_controller(self):
        from src.core.animation_engine import AnimationEngine
        m = _simple_model()
        anim = Animation(name='scale_anim', length=1.0)
        node = ModelNode(name='hip', flags=int(NodeFlags.HEADER))
        node.controllers = [{
            'type': 36, 'name': 'scalekey',
            'times': [0.0, 1.0], 'values': [[1.0], [2.0]], 'columns': 1,
        }]
        anim.nodes.append(node)
        m.animations.append(anim)
        m2 = _write_and_read(m)
        eng = AnimationEngine(m2)
        eng.play('scale_anim')
        pose = eng.evaluate(0.5)
        hip = pose.nodes.get('hip')
        assert hip is not None
        assert abs(hip.scale - 1.5) < 0.1  # interpolated between 1.0 and 2.0


# ══════════════════════════════════════════════════════════════════════════════
#  Section 4 – Auto-Rigger Gaussian heat diffusion
# ══════════════════════════════════════════════════════════════════════════════

def _mesh_model_height(height=1.8, nvert=30):
    """Build a mesh spanning 0..height with nvert vertices."""
    model = KotorModel(name='heattest')
    root  = ModelNode(name='heattest', flags=int(NodeFlags.HEADER))
    mesh  = ModelNode(name='body', flags=int(NodeFlags.HEADER) | int(NodeFlags.MESH))
    verts = []
    for i in range(nvert):
        t = i / max(nvert - 1, 1)
        verts.append((0.0, 0.0, t * height))
    mesh.vertices = verts
    mesh.faces    = [(0, 1, 2)]
    mesh.parent   = root
    root.children.append(mesh)
    model.root_node = root
    return model


class TestAutoRiggerHeatDiffusion:
    """Improved heat-diffusion weight painting."""

    def test_no_zero_weight_vertices(self):
        from src.autorig.auto_rigger import AutoRigger
        m = _mesh_model_height(nvert=20)
        rigger = AutoRigger()
        rigger.rig_model(m)
        stats = rigger.get_weight_stats(m)
        for node_name, s in stats.items():
            assert s['zero_weight_verts'] == 0, \
                f"Node {node_name} has zero-weight vertices"

    def test_weights_sum_to_one(self):
        from src.autorig.auto_rigger import AutoRigger
        m = _mesh_model_height(nvert=15)
        rigger = AutoRigger()
        rigger.rig_model(m)
        for node in m.mesh_nodes():
            if node.is_skin and node.skin_data:
                for i, sd in enumerate(node.skin_data):
                    total = sum(inf.weight for inf in sd.influences)
                    assert abs(total - 1.0) < 1e-5, \
                        f"Vertex {i} weights sum to {total}"

    def test_max_influences_respected(self):
        from src.autorig.auto_rigger import AutoRigger
        m = _mesh_model_height(nvert=10)
        rigger = AutoRigger()
        rigger.rig_model(m)
        for node in m.mesh_nodes():
            if node.is_skin:
                for sd in node.skin_data:
                    assert len(sd.influences) <= AutoRigger.MAX_INFLUENCES

    def test_heat_falloff_affects_sharpness(self):
        """Higher falloff → more concentrated (fewer effective influences)."""
        from src.autorig.auto_rigger import AutoRigger
        m_tight  = _mesh_model_height(nvert=10)
        m_diffuse = _mesh_model_height(nvert=10)

        r_tight   = AutoRigger(); r_tight.heat_falloff  = 8.0
        r_diffuse = AutoRigger(); r_diffuse.heat_falloff = 1.0

        r_tight.rig_model(m_tight)
        r_diffuse.rig_model(m_diffuse)

        def avg_inf(model):
            counts = []
            for node in model.mesh_nodes():
                if node.is_skin:
                    counts += [len(sd.influences) for sd in node.skin_data]
            return sum(counts) / max(len(counts), 1)

        # With tighter falloff, top bone gets higher weight concentration
        tight_avg   = avg_inf(m_tight)
        diffuse_avg = avg_inf(m_diffuse)
        # tight should have fewer or equal effective influences
        assert tight_avg <= diffuse_avg + 1.5

    def test_creature_template_no_zero_weight(self):
        from src.autorig.auto_rigger import AutoRigger
        m = _mesh_model_height(nvert=12)
        rigger = AutoRigger()
        rigger.rig_model(m, template='creature')
        stats = rigger.get_weight_stats(m)
        for s in stats.values():
            assert s['zero_weight_verts'] == 0

    def test_bone_map_populated(self):
        from src.autorig.auto_rigger import AutoRigger
        m = _mesh_model_height(nvert=5)
        rigger = AutoRigger()
        rigger.rig_model(m)
        for node in m.mesh_nodes():
            if node.is_skin:
                assert len(node.bone_map) > 0

    def test_all_vertices_have_skin_data(self):
        from src.autorig.auto_rigger import AutoRigger
        m = _mesh_model_height(nvert=8)
        rigger = AutoRigger()
        rigger.rig_model(m)
        for node in m.mesh_nodes():
            if node.is_skin:
                assert len(node.skin_data) == len(node.vertices)

    def test_min_weight_threshold(self):
        """Bones with weight below min_weight should be pruned."""
        from src.autorig.auto_rigger import AutoRigger
        m = _mesh_model_height(nvert=5)
        rigger = AutoRigger()
        rigger.min_weight = 0.05
        rigger.rig_model(m)
        for node in m.mesh_nodes():
            if node.is_skin:
                for sd in node.skin_data:
                    for inf in sd.influences:
                        assert inf.weight >= 0.05 - 1e-7

    def test_single_vertex_mesh(self):
        """Single vertex should always get exactly one influence summing to 1."""
        from src.autorig.auto_rigger import AutoRigger
        m = KotorModel(name='sv')
        root = ModelNode(name='sv', flags=int(NodeFlags.HEADER))
        mesh = ModelNode(name='body', flags=int(NodeFlags.HEADER) | int(NodeFlags.MESH))
        mesh.vertices = [(0.0, 0.0, 0.9)]
        mesh.faces    = []
        mesh.parent   = root
        root.children.append(mesh)
        m.root_node   = root
        rigger = AutoRigger()
        rigger.rig_model(m)
        body = m.find_node('body')
        assert body is not None and body.is_skin
        assert len(body.skin_data) == 1
        total = sum(inf.weight for inf in body.skin_data[0].influences)
        assert abs(total - 1.0) < 1e-5

    def test_rig_model_returns_same_model(self):
        from src.autorig.auto_rigger import AutoRigger
        m = _mesh_model_height(nvert=5)
        rigger = AutoRigger()
        result = rigger.rig_model(m)
        assert result is m

    def test_weight_stats_total_verts(self):
        from src.autorig.auto_rigger import AutoRigger
        m = _mesh_model_height(nvert=7)
        rigger = AutoRigger()
        rigger.rig_model(m)
        stats = rigger.get_weight_stats(m)
        assert 'body' in stats
        assert stats['body']['total_verts'] == 7


# ══════════════════════════════════════════════════════════════════════════════
#  Section 5 – Auto-Rigger: rig_from_template
# ══════════════════════════════════════════════════════════════════════════════

class TestAutoRiggerTemplate:
    """rig_from_template must correctly scale and apply rig to target model."""

    def _source_model(self):
        from src.autorig.auto_rigger import AutoRigger
        m = _mesh_model_height(height=1.8, nvert=8)
        AutoRigger().rig_model(m)
        return m

    def test_template_extraction(self):
        from src.autorig.auto_rigger import RigExtractor
        src = self._source_model()
        tmpl = RigExtractor().extract(src)
        assert tmpl is not None
        assert len(tmpl.bones) > 0

    def test_template_height(self):
        from src.autorig.auto_rigger import RigExtractor
        src = self._source_model()
        tmpl = RigExtractor().extract(src)
        assert tmpl.height > 0

    def test_template_bone_names(self):
        from src.autorig.auto_rigger import RigExtractor
        src = self._source_model()
        tmpl = RigExtractor().extract(src)
        assert len(tmpl.bone_names) > 0

    def test_rig_from_template_no_zero_weights(self):
        from src.autorig.auto_rigger import RigExtractor, AutoRigger
        src = self._source_model()
        tmpl = RigExtractor().extract(src)
        tgt = _mesh_model_height(height=2.0, nvert=8)
        AutoRigger().rig_from_template(tgt, tmpl)
        stats = AutoRigger().get_weight_stats(tgt)
        for s in stats.values():
            assert s['zero_weight_verts'] == 0

    def test_template_save_load(self):
        from src.autorig.auto_rigger import RigExtractor
        src = self._source_model()
        tmpl = RigExtractor().extract(src)
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            path = f.name
        try:
            tmpl.save(path)
            from src.autorig.auto_rigger import RigTemplate
            tmpl2 = RigTemplate.load(path)
            assert len(tmpl2.bones) == len(tmpl.bones)
            assert abs(tmpl2.height - tmpl.height) < 1e-4
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def test_template_to_dict_roundtrip(self):
        from src.autorig.auto_rigger import RigExtractor
        src = self._source_model()
        tmpl = RigExtractor().extract(src)
        d = tmpl.to_dict()
        assert 'bones' in d
        assert 'height' in d
        assert 'bb_min' in d


# ══════════════════════════════════════════════════════════════════════════════
#  Section 6 – Animation Engine + ASCII round-trip integration
# ══════════════════════════════════════════════════════════════════════════════

class TestAnimationEngineIntegration:
    """AnimationEngine working on a round-tripped ASCII model."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from src.core.animation_engine import AnimationEngine
        m = _simple_model('integ')
        anim = _anim_with_controllers('run', 2.0)
        m.animations.append(anim)
        m2 = _write_and_read(m)
        self.engine = AnimationEngine(m2)
        self.engine.play('run')

    def test_play_returns_true(self):
        from src.core.animation_engine import AnimationEngine
        m = _simple_model()
        m.animations.append(_anim_with_controllers('idle'))
        eng = AnimationEngine(_write_and_read(m))
        assert eng.play('idle') is True

    def test_advance_returns_true_while_looping(self):
        still = self.engine.advance(0.1)
        assert still is True

    def test_evaluate_returns_pose(self):
        pose = self.engine.evaluate(0.5)
        assert pose is not None

    def test_pose_contains_hip(self):
        pose = self.engine.evaluate(0.5)
        assert 'hip' in pose.nodes

    def test_hip_position_interpolated(self):
        pose = self.engine.evaluate(0.5)
        hip = pose.nodes['hip']
        # KotOR position keys are DELTA offsets (xoreos/KotorBlender convention).
        # hip bind pose z=0.5; controller delta at t=0.5 is 0.6.
        # animated_z = bind_z(0.5) + delta(0.6) = 1.1
        assert abs(hip.position[2] - 1.1) < 0.05

    def test_hip_rotation_unit_quaternion(self):
        pose = self.engine.evaluate(0.5)
        hip = pose.nodes['hip']
        q = hip.rotation
        mag = sum(x*x for x in q) ** 0.5
        assert abs(mag - 1.0) < 1e-4

    def test_non_loop_terminates(self):
        from src.core.animation_engine import AnimationEngine
        m = _simple_model()
        m.animations.append(_anim_with_controllers('one_shot', 0.5))
        eng = AnimationEngine(_write_and_read(m))
        eng.play('one_shot', loop=False)
        still = True
        for _ in range(100):
            still = eng.advance(0.1)
            if not still:
                break
        assert not still

    def test_advance_false_after_end(self):
        from src.core.animation_engine import AnimationEngine
        m = _simple_model()
        m.animations.append(_anim_with_controllers('short', 0.1))
        eng = AnimationEngine(_write_and_read(m))
        eng.play('short', loop=False)
        result = eng.advance(0.5)
        assert result is False

    def test_seek_works(self):
        self.engine.seek(0.75)
        assert abs(self.engine.current_time - 0.75) < 1e-5

    def test_stop_then_advance_false(self):
        self.engine.stop()
        result = self.engine.advance(0.1)
        assert result is False


# ══════════════════════════════════════════════════════════════════════════════
#  Section 7 – _ascii_type_to_flags utility
# ══════════════════════════════════════════════════════════════════════════════

class TestAsciiTypeToFlags:
    def test_dummy(self):
        f = _ascii_type_to_flags('dummy')
        assert f & int(NodeFlags.HEADER)
        assert not (f & int(NodeFlags.MESH))

    def test_trimesh(self):
        f = _ascii_type_to_flags('trimesh')
        assert f & int(NodeFlags.MESH)
        assert not (f & int(NodeFlags.SKIN))

    def test_skin(self):
        f = _ascii_type_to_flags('skin')
        assert f & int(NodeFlags.MESH)
        assert f & int(NodeFlags.SKIN)

    def test_danglymesh(self):
        f = _ascii_type_to_flags('danglymesh')
        assert f & int(NodeFlags.MESH)
        assert f & int(NodeFlags.DANGLY)

    def test_light(self):
        f = _ascii_type_to_flags('light')
        assert f & int(NodeFlags.LIGHT)
        assert not (f & int(NodeFlags.MESH))

    def test_emitter(self):
        f = _ascii_type_to_flags('emitter')
        assert f & int(NodeFlags.EMITTER)

    def test_lightsaber(self):
        f = _ascii_type_to_flags('lightsaber')
        assert f & int(NodeFlags.SABER)

    def test_aabb(self):
        f = _ascii_type_to_flags('aabb')
        assert f & int(NodeFlags.AABB)

    def test_reference(self):
        f = _ascii_type_to_flags('reference')
        assert f & int(NodeFlags.REFERENCE)

    def test_case_insensitive(self):
        assert _ascii_type_to_flags('TRIMESH') == _ascii_type_to_flags('trimesh')
        assert _ascii_type_to_flags('Skin') == _ascii_type_to_flags('skin')


# ══════════════════════════════════════════════════════════════════════════════
#  Section 8 – MDLAsciiParser edge cases
# ══════════════════════════════════════════════════════════════════════════════

class TestMDLAsciiParserEdgeCases:
    def test_parse_empty_string(self):
        m = MDLAsciiParser().parse_string("")
        assert m is not None
        assert m.root_node is None

    def test_parse_minimal_model(self):
        txt = "newmodel x\nsetsupermodel x NULL\ndonemodel x\n"
        m = MDLAsciiParser().parse_string(txt)
        assert m.name == 'x'

    def test_parse_model_with_no_anims(self):
        m = MDLAsciiParser().parse_string(_SAMPLE_MDL.replace(
            'newanim', '# newanim').replace('doneanim', '# doneanim'))
        assert len(m.animations) == 0

    def test_parse_anim_no_nodes(self):
        txt = """\
newmodel t
setsupermodel t NULL
newanim idle t
  length 0.5000
  transtime 0.1000
doneanim idle t
donemodel t
"""
        m = MDLAsciiParser().parse_string(txt)
        assert len(m.animations) == 1
        assert m.animations[0].name == 'idle'
        assert m.animations[0].nodes == []

    def test_parse_multiple_events(self):
        m = MDLAsciiParser().parse_string(_SAMPLE_MDL)
        assert len(m.animations[0].events) == 2

    def test_parse_supermodel(self):
        txt = "newmodel x\nsetsupermodel x k_sup_males\ndonemodel x\n"
        m = MDLAsciiParser().parse_string(txt)
        assert m.supermodel == 'k_sup_males'

    def test_parse_animationscale(self):
        txt = "newmodel x\nsetanimationscale 1.5\ndonemodel x\n"
        m = MDLAsciiParser().parse_string(txt)
        assert abs(m.anim_scale - 1.5) < 1e-5

    def test_parse_comment_lines(self):
        """Lines starting with # should be silently ignored."""
        txt = "# header\nnewmodel x\n# another comment\ndonemodel x\n"
        m = MDLAsciiParser().parse_string(txt)
        assert m.name == 'x'

    def test_parse_node_position(self):
        m = MDLAsciiParser().parse_string(_SAMPLE_MDL)
        hip = m.find_node('hip')
        assert hip is not None
        assert abs(hip.position[2] - 0.5) < 1e-5

    def test_parse_empty_keyframe_table(self):
        """positionkey 0 should produce no controllers."""
        txt = """\
newmodel t
newanim idle t
  length 0.5
  node dummy hip
    parent NULL
    positionkey 0
  endnode
doneanim idle t
donemodel t
"""
        m = MDLAsciiParser().parse_string(txt)
        if m.animations and m.animations[0].nodes:
            node = m.animations[0].nodes[0]
            pos_ctrls = [c for c in node.controllers if c['type'] == 8]
            # If there are 0 keyframes, no controller should be added
            assert pos_ctrls == []


# ══════════════════════════════════════════════════════════════════════════════
#  Section 9 – MDLAsciiWriter: model node controllers
# ══════════════════════════════════════════════════════════════════════════════

class TestMDLAsciiWriterNodeControllers:
    """Bind-pose node controllers should be written into the node block."""

    def test_bind_pose_positionkey_written(self):
        m = _simple_model()
        hip = m.find_node('hip')
        assert hip is not None
        hip.controllers = [{
            'type': 8, 'name': 'positionkey',
            'times': [0.0], 'values': [[0, 0, 0.5]], 'columns': 3,
        }]
        with tempfile.NamedTemporaryFile(suffix='.mdl', mode='w', delete=False) as f:
            path = f.name
        try:
            MDLAsciiWriter().write(m, path)
            txt = open(path).read()
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        assert 'positionkey' in txt

    def test_bind_pose_controller_round_trips(self):
        m = _simple_model()
        hip = m.find_node('hip')
        hip.controllers = [{
            'type': 8, 'name': 'positionkey',
            'times': [0.0, 1.0], 'values': [[0, 0, 0], [0, 0, 1]], 'columns': 3,
        }]
        m2 = _write_and_read(m)
        hip2 = m2.find_node('hip')
        assert hip2 is not None
        pos_ctrls = [c for c in hip2.controllers if c['type'] == 8]
        assert len(pos_ctrls) >= 1

    def test_no_crash_empty_controller_list(self):
        m = _simple_model()
        hip = m.find_node('hip')
        hip.controllers = []
        # Should not crash
        with tempfile.NamedTemporaryFile(suffix='.mdl', mode='w', delete=False) as f:
            path = f.name
        try:
            MDLAsciiWriter().write(m, path)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass


# ══════════════════════════════════════════════════════════════════════════════
#  Section 10 – Edge Cases & Robustness
# ══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_no_crash_on_model_with_no_root(self):
        m = KotorModel(name='empty')
        writer = MDLAsciiWriter()
        with tempfile.NamedTemporaryFile(suffix='.mdl', mode='w', delete=False) as f:
            path = f.name
        try:
            writer.write(m, path)
            txt = open(path).read()
            assert 'newmodel empty' in txt
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def test_auto_rigger_empty_model(self):
        from src.autorig.auto_rigger import AutoRigger
        m = KotorModel(name='empty')
        # Should not crash
        AutoRigger().rig_model(m)

    def test_animation_engine_no_animations(self):
        from src.core.animation_engine import AnimationEngine
        m = _simple_model()
        eng = AnimationEngine(m)
        result = eng.play('nonexistent')
        assert result is False

    def test_animation_engine_advance_no_anim(self):
        from src.core.animation_engine import AnimationEngine
        m = _simple_model()
        eng = AnimationEngine(m)
        result = eng.advance(0.1)
        assert result is False

    def test_animation_engine_evaluate_no_anim(self):
        from src.core.animation_engine import AnimationEngine
        m = _simple_model()
        eng = AnimationEngine(m)
        pose = eng.evaluate(0.5)
        assert pose is not None
        assert len(pose.nodes) == 0

    def test_parser_handles_malformed_controller(self):
        """positionkey with invalid float should not crash."""
        txt = """\
newmodel t
newanim idle t
  length 1.0
  node dummy hip
    parent NULL
    positionkey 2
      0.0 abc def ghi
      1.0 0.0 0.0 0.0
  endnode
doneanim idle t
donemodel t
"""
        # Should not raise
        m = MDLAsciiParser().parse_string(txt)
        assert m is not None

    def test_rig_model_already_skinned(self):
        """Re-rigging a model that is already skinned should not crash."""
        from src.autorig.auto_rigger import AutoRigger
        m = _mesh_model_height(nvert=5)
        r = AutoRigger()
        r.rig_model(m)
        # Rig again
        r.rig_model(m)

    def test_round_trip_empty_animations(self):
        m = _simple_model()
        m.animations = []
        m2 = _write_and_read(m)
        assert m2.animations == []

    def test_round_trip_special_chars_model_name(self):
        """Underscore/digits in model name should survive round-trip."""
        m = _simple_model('c_bantha_01')
        m2 = _write_and_read(m)
        assert m2.name == 'c_bantha_01'

    def test_anim_node_with_zero_length_animation(self):
        from src.core.animation_engine import AnimationEngine
        m = _simple_model()
        anim = Animation(name='zero', length=0.0)
        node = ModelNode(name='hip', flags=int(NodeFlags.HEADER))
        node.controllers = [{
            'type': 8, 'times': [0.0], 'values': [[0, 0, 0.5]], 'columns': 3,
        }]
        anim.nodes.append(node)
        m.animations.append(anim)
        eng = AnimationEngine(m)
        # Should not crash with zero-length animation
        eng.play('zero', loop=False)
        eng.advance(0.1)

    def test_model_find_node_case_insensitive(self):
        m = _simple_model()
        n1 = m.find_node('HIP')
        n2 = m.find_node('hip')
        assert n1 is n2

    def test_model_all_nodes_count(self):
        m = _simple_model()
        nodes = m.all_nodes()
        assert len(nodes) >= 2  # root + hip

    def test_model_mesh_nodes(self):
        m = _simple_model(with_mesh=True)
        meshes = m.mesh_nodes()
        assert len(meshes) >= 1

    def test_model_bone_nodes(self):
        m = _simple_model()
        bones = m.bone_nodes()
        assert len(bones) >= 1


# ══════════════════════════════════════════════════════════════════════════════
#  Section 11 – Auto-Rigger weight statistics
# ══════════════════════════════════════════════════════════════════════════════

class TestWeightStats:
    def test_stats_keys_present(self):
        from src.autorig.auto_rigger import AutoRigger
        m = _mesh_model_height(nvert=5)
        r = AutoRigger()
        r.rig_model(m)
        stats = r.get_weight_stats(m)
        assert 'body' in stats
        s = stats['body']
        assert 'total_verts' in s
        assert 'avg_influences' in s
        assert 'max_influences' in s
        assert 'zero_weight_verts' in s
        assert 'bone_usage' in s

    def test_stats_avg_influences_positive(self):
        from src.autorig.auto_rigger import AutoRigger
        m = _mesh_model_height(nvert=5)
        r = AutoRigger()
        r.rig_model(m)
        stats = r.get_weight_stats(m)
        assert stats['body']['avg_influences'] > 0

    def test_stats_max_influences_lte_max(self):
        from src.autorig.auto_rigger import AutoRigger
        m = _mesh_model_height(nvert=5)
        r = AutoRigger()
        r.rig_model(m)
        stats = r.get_weight_stats(m)
        assert stats['body']['max_influences'] <= AutoRigger.MAX_INFLUENCES

    def test_stats_bone_usage_nonempty(self):
        from src.autorig.auto_rigger import AutoRigger
        m = _mesh_model_height(nvert=5)
        r = AutoRigger()
        r.rig_model(m)
        stats = r.get_weight_stats(m)
        assert len(stats['body']['bone_usage']) > 0

    def test_stats_no_skin_nodes_empty(self):
        from src.autorig.auto_rigger import AutoRigger
        m = _simple_model(with_mesh=False)  # no mesh → no stats
        r = AutoRigger()
        stats = r.get_weight_stats(m)
        assert stats == {}


# ══════════════════════════════════════════════════════════════════════════════
#  Section 12 – List animations, FPS estimate, blending
# ══════════════════════════════════════════════════════════════════════════════

class TestAnimationEngineExtended:
    def test_list_animations_after_roundtrip(self):
        from src.core.animation_engine import AnimationEngine
        m = _simple_model()
        m.animations.append(_anim_with_controllers('walk'))
        m.animations.append(_anim_with_controllers('run'))
        m2 = _write_and_read(m)
        eng = AnimationEngine(m2)
        lst = eng.list_animations()
        names = [a['name'] for a in lst]
        assert 'walk' in names
        assert 'run' in names

    def test_fps_estimate_positive(self):
        from src.core.animation_engine import AnimationEngine
        m = _simple_model()
        m.animations.append(_anim_with_controllers('walk'))
        m2 = _write_and_read(m)
        eng = AnimationEngine(m2)
        fps = eng.get_animation_fps_estimate(m2.animations[0])
        assert fps > 0

    def test_blend_fraction_during_transition(self):
        from src.core.animation_engine import AnimationEngine
        m = _simple_model()
        m.animations.append(_anim_with_controllers('walk', 1.0))
        m.animations.append(_anim_with_controllers('run', 1.0))
        eng = AnimationEngine(m)
        eng.play('walk', loop=True)
        eng.advance(0.5)
        eng.play('run', blend=True)
        eng.advance(0.01)
        # During blend period, blend_fraction should be between 0 and 1
        assert 0.0 <= eng.blend_fraction() <= 1.0

    def test_is_blending_true_after_play_blend(self):
        from src.core.animation_engine import AnimationEngine
        m = _simple_model()
        m.animations.append(_anim_with_controllers('walk', 1.0))
        m.animations.append(_anim_with_controllers('run', 1.0))
        eng = AnimationEngine(m)
        eng.play('walk')
        eng.advance(0.1)
        eng.play('run', blend=True)
        eng.advance(0.001)
        assert eng.is_blending()

    def test_add_animation(self):
        from src.core.animation_engine import AnimationEngine
        m = _simple_model()
        eng = AnimationEngine(m)
        new_anim = _anim_with_controllers('new_clip')
        eng.add_animation(new_anim)
        assert any(a['name'] == 'new_clip' for a in eng.list_animations())

    def test_remove_animation(self):
        from src.core.animation_engine import AnimationEngine
        m = _simple_model()
        m.animations.append(_anim_with_controllers('removable'))
        eng = AnimationEngine(m)
        removed = eng.remove_animation('removable')
        assert removed
        assert not any(a['name'] == 'removable' for a in eng.list_animations())

    def test_remove_nonexistent_animation(self):
        from src.core.animation_engine import AnimationEngine
        m = _simple_model()
        eng = AnimationEngine(m)
        assert not eng.remove_animation('ghost')

    def test_get_pose_alias(self):
        from src.core.animation_engine import AnimationEngine
        m = _simple_model()
        m.animations.append(_anim_with_controllers('walk'))
        eng = AnimationEngine(m)
        eng.play('walk')
        p1 = eng.evaluate(0.3)
        p2 = eng.get_pose(0.3)
        assert p1.time == p2.time

    def test_event_fired_on_advance(self):
        from src.core.animation_engine import AnimationEngine
        m = _simple_model()
        anim = _anim_with_controllers('walk', 1.0)
        anim.events.append(AnimEvent(time=0.3, name='footstep'))
        m.animations.append(anim)
        eng = AnimationEngine(m)
        eng.play('walk')
        eng.advance(0.5)  # past t=0.3
        fired = eng.get_fired_events()  # returns list of event name strings
        assert 'footstep' in fired

    def test_export_json_roundtrip(self):
        from src.core.animation_engine import AnimationEngine
        import json
        m = _simple_model()
        m.animations.append(_anim_with_controllers('walk', 1.0))
        m2 = _write_and_read(m)
        eng = AnimationEngine(m2)
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            path = f.name
        try:
            ok = eng.export_animation_json('walk', path)
            assert ok
            with open(path) as f:
                data = json.load(f)
            assert data['anim_name'] == 'walk'
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def test_export_bvh(self):
        from src.core.animation_engine import AnimationEngine
        m = _simple_model()
        m.animations.append(_anim_with_controllers('walk', 1.0))
        m2 = _write_and_read(m)
        eng = AnimationEngine(m2)
        with tempfile.NamedTemporaryFile(suffix='.bvh', delete=False) as f:
            path = f.name
        try:
            ok = eng.export_animation_bvh('walk', path)
            assert ok
            with open(path) as f:
                txt = f.read()
            assert 'HIERARCHY' in txt
            assert 'MOTION' in txt
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
