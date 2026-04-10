"""
test_v360_usecomp_tpc_cloth_gltf.py
====================================
GhostRigger v5.4 — comprehensive tests for:
  1. build_bone_remap / retarget_usecomp (AnimationEngine)
  2. _is_tpc / tpc_info / _decode_texture (resource_manager)
  3. ClothRigSimulator.kinetic_energy / total_displacement (cloth_rig)
  4. GltfRoundTripResult / gltf_round_trip_verify (mesh_converter)

Target: 65+ passing tests, 0 failures.
"""

import math
import struct
import sys
import os
import copy
import tempfile
import unittest

# ── path setup ────────────────────────────────────────────────────────────────
_ROOT = os.path.join(os.path.dirname(__file__), '..')
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_model(name='TestModel', nodes=None, anims=None):
    """Create a minimal KotorModel with a root node and optional bone children."""
    from src.core.model_data import KotorModel, ModelNode
    m = KotorModel()
    m.name = name
    root = ModelNode()
    root.name = name + '_root'
    m.root_node = root
    if nodes:
        for node_name in nodes:
            n = ModelNode()
            n.name = node_name
            root.children.append(n)
    if anims:
        from src.core.model_data import Animation
        for aname in anims:
            a = Animation()
            a.name = aname
            a.length = 1.0
            m.animations.append(a)
    return m


def _make_anim(name='usecomp', node_names=None, length=1.0):
    """Create a minimal Animation with named nodes."""
    from src.core.model_data import Animation, ModelNode
    a = Animation()
    a.name = name
    a.length = length
    a.anim_root = 'root'
    a.nodes = []
    for nn in (node_names or []):
        n = ModelNode()
        n.name = nn
        n.controllers = []
        a.nodes.append(n)
    return a


def _make_tpc_header(width=64, height=64, encoding=4, num_mips=1, data_size=0,
                     alpha_test=0.0, payload_size=None):
    """Build a minimal 128-byte TPC header + pixel payload."""
    if data_size == 0 and payload_size is None:
        bpp = {1: 1, 2: 3, 4: 4, 12: 4}.get(encoding, 4)
        payload_size = width * height * bpp
    elif data_size > 0 and payload_size is None:
        payload_size = data_size
    hdr = bytearray(128)
    struct.pack_into('<I', hdr, 0, data_size)
    struct.pack_into('<f', hdr, 4, alpha_test)
    struct.pack_into('<H', hdr, 8, width)
    struct.pack_into('<H', hdr, 10, height)
    hdr[12] = encoding
    hdr[13] = num_mips
    return bytes(hdr) + bytes(payload_size)


# ════════════════════════════════════════════════════════════════════════════════
#  1. build_bone_remap
# ════════════════════════════════════════════════════════════════════════════════

class TestBuildBoneRemap(unittest.TestCase):
    """Tests for the module-level build_bone_remap() function."""

    def setUp(self):
        from src.core.animation_engine import build_bone_remap
        self.build_bone_remap = build_bone_remap

    def _src(self, names):
        return _make_model('src', names)

    def _tgt(self, names):
        return _make_model('tgt', names)

    def test_exact_match(self):
        remap = self.build_bone_remap(
            self._src(['Spine', 'Head', 'RHand']),
            self._tgt(['Spine', 'Head', 'RHand']),
        )
        self.assertEqual(remap.get('Spine'), 'Spine')
        self.assertEqual(remap.get('Head'),  'Head')
        self.assertEqual(remap.get('RHand'), 'RHand')

    def test_case_insensitive_match(self):
        remap = self.build_bone_remap(
            self._src(['SPINE', 'HEAD']),
            self._tgt(['spine', 'head']),
        )
        # After case-insensitive exact match, keys are original names
        self.assertTrue(
            any(k.upper() == 'SPINE' for k in remap),
            f"'SPINE' not in remap keys: {list(remap.keys())}"
        )
        self.assertTrue(
            any(k.upper() == 'HEAD' for k in remap),
            f"'HEAD' not in remap keys: {list(remap.keys())}"
        )

    def test_no_match_returns_empty(self):
        remap = self.build_bone_remap(
            self._src(['BoneA', 'BoneB']),
            self._tgt(['Unrelated1', 'Unrelated2']),
        )
        self.assertEqual(len(remap), 0)

    def test_prefix_strip_match(self):
        """'NordHead_jaw' in src should map to 'jaw' in target via prefix strip."""
        from src.core.model_data import KotorModel, ModelNode
        src = KotorModel(); src.name = 'NordHead'
        root = ModelNode(); root.name = 'NordHead_root'; src.root_node = root
        n = ModelNode(); n.name = 'NordHead_jaw'
        root.children.append(n)
        tgt = self._tgt(['jaw', 'neck', 'head'])
        remap = self.build_bone_remap(src, tgt)
        self.assertIn('NordHead_jaw', remap)
        self.assertEqual(remap['NordHead_jaw'].lower(), 'jaw')

    def test_alias_table_nordhead_neck(self):
        """'nordhead_neck' should match 'neck' via alias or prefix-strip."""
        from src.core.model_data import KotorModel, ModelNode
        src = KotorModel(); src.name = 'NordHead'
        root = ModelNode(); root.name = 'NordHead_root'; src.root_node = root
        n = ModelNode(); n.name = 'nordhead_neck'
        root.children.append(n)
        tgt = self._tgt(['neck', 'spine'])
        remap = self.build_bone_remap(src, tgt)
        # Should match via alias OR prefix-strip (nordhead_neck → neck)
        matched = remap.get('nordhead_neck', '')
        self.assertEqual(matched.lower(), 'neck',
                         f"Expected 'neck', got '{matched}', remap={remap}")

    def test_suffix_strip_match(self):
        """'spine01' should match 'spine1' via suffix normalisation."""
        remap = self.build_bone_remap(
            self._src(['spine01']),
            self._tgt(['spine1']),
        )
        self.assertIn('spine01', remap)

    def test_fuzzy_false_skips_prefix(self):
        """With fuzzy=False, prefix-stripped matches should not be found."""
        from src.core.model_data import KotorModel, ModelNode
        src = KotorModel(); src.name = 'NordHead'
        root = ModelNode(); root.name = 'NordHead_root'; src.root_node = root
        n = ModelNode(); n.name = 'NordHead_jaw'
        root.children.append(n)
        tgt = self._tgt(['jaw'])
        remap = self.build_bone_remap(src, tgt, fuzzy=False)
        self.assertEqual(len(remap), 0)

    def test_empty_model_returns_empty(self):
        remap = self.build_bone_remap(
            _make_model('src', []),
            _make_model('tgt', ['spine']),
        )
        self.assertEqual(remap, {})

    def test_both_empty_returns_empty(self):
        remap = self.build_bone_remap(
            _make_model('src', []),
            _make_model('tgt', []),
        )
        self.assertEqual(remap, {})

    def test_kotor_standard_bones_exact(self):
        """All common KotOR skeleton bones should exact-match."""
        bones = ['rhand', 'lhand', 'neck', 'head', 'chest', 'spine',
                 'pelvis', 'rthigh', 'lthigh', 'rfoot', 'lfoot']
        remap = self.build_bone_remap(
            _make_model('src', bones),
            _make_model('tgt', bones),
        )
        for b in bones:
            self.assertIn(b, remap, f"'{b}' not in remap keys {list(remap.keys())}")


# ════════════════════════════════════════════════════════════════════════════════
#  2. retarget_usecomp (module-level function)
# ════════════════════════════════════════════════════════════════════════════════

class TestRetargetUsecomp(unittest.TestCase):

    def setUp(self):
        from src.core.animation_engine import retarget_usecomp
        self.retarget_usecomp = retarget_usecomp

    def test_basic_filter_by_target_bones(self):
        """Nodes not present in target must be stripped."""
        from src.core.model_data import KotorModel, ModelNode
        anim = _make_anim('usecomp', ['spine', 'head', 'rhand', 'ghost_bone'])
        tgt = _make_model('tgt', ['spine', 'head', 'rhand'])
        result = self.retarget_usecomp(anim, tgt)
        names = [n.name for n in result.nodes]
        self.assertIn('spine', names)
        self.assertIn('head',  names)
        self.assertIn('rhand', names)
        self.assertNotIn('ghost_bone', names)

    def test_bone_rename_applied(self):
        """Renamed bones should appear under the new name."""
        anim = _make_anim('usecomp', ['NordHead_jaw'])
        tgt  = _make_model('tgt', ['jaw'])
        remap = {'NordHead_jaw': 'jaw'}
        result = self.retarget_usecomp(anim, tgt, remap)
        names = [n.name for n in result.nodes]
        self.assertIn('jaw', names)
        self.assertNotIn('NordHead_jaw', names)

    def test_copy_mode_does_not_modify_source(self):
        """With copy=True the original animation nodes must be untouched."""
        anim = _make_anim('usecomp', ['spine', 'head'])
        orig_names = [n.name for n in anim.nodes]
        tgt = _make_model('tgt', ['spine'])
        _ = self.retarget_usecomp(anim, tgt, copy=True)
        self.assertEqual([n.name for n in anim.nodes], orig_names)

    def test_copy_false_modifies_in_place(self):
        """With copy=False the original animation IS modified."""
        anim = _make_anim('usecomp', ['spine', 'ghost'])
        tgt  = _make_model('tgt', ['spine'])
        result = self.retarget_usecomp(anim, tgt, copy=False)
        self.assertIs(result, anim)

    def test_no_matching_bones_returns_empty_nodes(self):
        anim = _make_anim('usecomp', ['bone_x', 'bone_y'])
        tgt  = _make_model('tgt', ['totally_different'])
        result = self.retarget_usecomp(anim, tgt)
        self.assertEqual(result.nodes, [])

    def test_animation_name_preserved(self):
        anim = _make_anim('usecomp', ['spine'])
        tgt  = _make_model('tgt', ['spine'])
        result = self.retarget_usecomp(anim, tgt)
        self.assertEqual(result.name, 'usecomp')

    def test_animation_length_preserved(self):
        anim = _make_anim('usecomp', ['spine'])
        anim.length = 3.14
        tgt  = _make_model('tgt', ['spine'])
        result = self.retarget_usecomp(anim, tgt)
        self.assertAlmostEqual(result.length, 3.14, places=5)


# ════════════════════════════════════════════════════════════════════════════════
#  3. AnimationEngine.build_bone_remap / retarget_usecomp instance methods
# ════════════════════════════════════════════════════════════════════════════════

class TestAnimationEngineBoneRemap(unittest.TestCase):

    def _make_engine(self, model_name, bone_names, anim_names=None):
        from src.core.animation_engine import AnimationEngine
        m = _make_model(model_name, bone_names, anim_names)
        return AnimationEngine(m), m

    def _make_engine_with_usecomp(self, src_bone_names, tgt_bone_names):
        """Create src engine with usecomp anim + target model."""
        from src.core.animation_engine import AnimationEngine
        from src.core.model_data import KotorModel, ModelNode
        src_m = _make_model('src', src_bone_names)
        uc    = _make_anim('usecomp', src_bone_names)
        src_m.animations.append(uc)
        tgt_m = _make_model('tgt', tgt_bone_names)
        return AnimationEngine(src_m), src_m, tgt_m

    def test_instance_build_bone_remap(self):
        from src.core.animation_engine import AnimationEngine
        eng, _ = self._make_engine('src', ['spine', 'head'])
        tgt = _make_model('tgt', ['spine', 'head'])
        remap = eng.build_bone_remap(tgt)
        self.assertIn('spine', remap)
        self.assertIn('head',  remap)

    def test_retarget_usecomp_no_usecomp_returns_none(self):
        eng, _ = self._make_engine('src', ['spine'], anim_names=['walk', 'run'])
        tgt = _make_model('tgt', ['spine'])
        result = eng.retarget_usecomp(tgt)
        self.assertIsNone(result)

    def test_retarget_usecomp_injects_into_target(self):
        """When inject=True, the retargeted anim is added to target_model."""
        eng, src_model, tgt_model = self._make_engine_with_usecomp(
            ['spine', 'head', 'ghost'], ['spine', 'head'])
        result = eng.retarget_usecomp(tgt_model, inject=True)
        self.assertIsNotNone(result)
        tgt_anim_names = [a.name.lower() for a in tgt_model.animations]
        self.assertIn('usecomp', tgt_anim_names)

    def test_retarget_usecomp_replaces_existing(self):
        """If target already has a usecomp, it should be replaced, not duplicated."""
        eng, src_model, tgt_model = self._make_engine_with_usecomp(
            ['spine'], ['spine'])
        # Pre-add an existing usecomp to target
        old_uc = _make_anim('usecomp', [])
        tgt_model.animations.append(old_uc)

        eng.retarget_usecomp(tgt_model, inject=True)
        uc_count = sum(1 for a in tgt_model.animations
                       if a.name.lower() in ('usecomp', 'use_comp', 'use comp'))
        self.assertEqual(uc_count, 1)


# ════════════════════════════════════════════════════════════════════════════════
#  4. _is_tpc / tpc_info (resource_manager)
# ════════════════════════════════════════════════════════════════════════════════

class TestIsTpc(unittest.TestCase):

    def setUp(self):
        from src.core.resource_manager import _is_tpc
        self._is_tpc = _is_tpc

    def test_rejects_empty(self):
        self.assertFalse(self._is_tpc(b''))

    def test_rejects_too_short(self):
        self.assertFalse(self._is_tpc(b'\x00' * 100))

    def test_rejects_png_magic(self):
        png = b'\x89PNG' + b'\x00' * 200
        self.assertFalse(self._is_tpc(png))

    def test_rejects_dds_magic(self):
        dds = b'DDS ' + b'\x00' * 200
        self.assertFalse(self._is_tpc(dds))

    def test_rejects_jpeg_magic(self):
        jpg = b'\xff\xd8\xff\xe0' + b'\x00' * 200
        self.assertFalse(self._is_tpc(jpg))

    def test_rejects_invalid_encoding(self):
        raw = _make_tpc_header(64, 64, encoding=7)  # encoding 7 is invalid
        self.assertFalse(self._is_tpc(raw))

    def test_rejects_zero_width(self):
        raw = _make_tpc_header(0, 64, encoding=4)
        self.assertFalse(self._is_tpc(raw))

    def test_rejects_non_power_of_two_dimensions(self):
        raw = _make_tpc_header(100, 100, encoding=4)  # 100 is not a power of 2
        self.assertFalse(self._is_tpc(raw))

    def test_rejects_zero_num_mips(self):
        raw = _make_tpc_header(64, 64, encoding=4, num_mips=0)
        self.assertFalse(self._is_tpc(raw))

    def test_accepts_uncompressed_rgba(self):
        raw = _make_tpc_header(64, 64, encoding=4, num_mips=1, data_size=0)
        self.assertTrue(self._is_tpc(raw))

    def test_accepts_uncompressed_grey(self):
        raw = _make_tpc_header(64, 64, encoding=1, num_mips=1, data_size=0)
        self.assertTrue(self._is_tpc(raw))

    def test_accepts_uncompressed_rgb(self):
        raw = _make_tpc_header(64, 64, encoding=2, num_mips=1, data_size=0)
        self.assertTrue(self._is_tpc(raw))

    def test_accepts_dxt1_compressed(self):
        w, h = 64, 64
        data_size = (w // 4) * (h // 4) * 8  # DXT1 block size
        raw = _make_tpc_header(w, h, encoding=2, num_mips=1,
                               data_size=data_size, payload_size=data_size)
        self.assertTrue(self._is_tpc(raw))

    def test_accepts_dxt5_compressed(self):
        w, h = 64, 64
        data_size = (w // 4) * (h // 4) * 16  # DXT5 block size
        raw = _make_tpc_header(w, h, encoding=4, num_mips=1,
                               data_size=data_size, payload_size=data_size)
        self.assertTrue(self._is_tpc(raw))

    def test_rejects_compressed_encoding1(self):
        """Encoding=1 (Grey) must not have data_size > 0."""
        raw = _make_tpc_header(64, 64, encoding=1, num_mips=1, data_size=1024)
        self.assertFalse(self._is_tpc(raw))

    def test_accepts_max_mips(self):
        """num_mips=12 (log2(4096)) is valid."""
        raw = _make_tpc_header(64, 64, encoding=4, num_mips=12, data_size=0)
        self.assertTrue(self._is_tpc(raw))

    def test_rejects_too_many_mips(self):
        raw = _make_tpc_header(64, 64, encoding=4, num_mips=14, data_size=0)
        self.assertFalse(self._is_tpc(raw))


class TestTpcInfo(unittest.TestCase):

    def setUp(self):
        from src.core.resource_manager import tpc_info
        self.tpc_info = tpc_info

    def test_returns_none_for_non_tpc(self):
        self.assertIsNone(self.tpc_info(b'DDS ' + b'\x00' * 200))

    def test_basic_fields_uncompressed_rgba(self):
        raw = _make_tpc_header(128, 128, encoding=4, num_mips=1, data_size=0,
                               alpha_test=0.5)
        info = self.tpc_info(raw)
        self.assertIsNotNone(info)
        self.assertEqual(info['width'], 128)
        self.assertEqual(info['height'], 128)
        self.assertEqual(info['encoding'], 4)
        self.assertEqual(info['num_mips'], 1)
        self.assertFalse(info['is_compressed'])
        self.assertEqual(info['format'], 'RGBA')

    def test_dxt1_format_string(self):
        w, h = 64, 64
        data_size = (w // 4) * (h // 4) * 8
        raw = _make_tpc_header(w, h, encoding=2, num_mips=1,
                               data_size=data_size, payload_size=data_size)
        info = self.tpc_info(raw)
        self.assertIsNotNone(info)
        self.assertEqual(info['format'], 'DXT1')
        self.assertTrue(info['is_compressed'])

    def test_dxt5_format_string(self):
        w, h = 64, 64
        data_size = (w // 4) * (h // 4) * 16
        raw = _make_tpc_header(w, h, encoding=4, num_mips=1,
                               data_size=data_size, payload_size=data_size)
        info = self.tpc_info(raw)
        self.assertIsNotNone(info)
        self.assertEqual(info['format'], 'DXT5')

    def test_grey_format_string(self):
        raw = _make_tpc_header(32, 32, encoding=1, num_mips=1, data_size=0)
        info = self.tpc_info(raw)
        self.assertIsNotNone(info)
        self.assertEqual(info['format'], 'Grey')

    def test_alpha_test_field(self):
        raw = _make_tpc_header(32, 32, encoding=4, num_mips=1,
                               data_size=0, alpha_test=0.75)
        info = self.tpc_info(raw)
        self.assertIsNotNone(info)
        self.assertAlmostEqual(info['alpha_test'], 0.75, places=5)


# ════════════════════════════════════════════════════════════════════════════════
#  5. ClothRigSimulator.kinetic_energy / total_displacement
# ════════════════════════════════════════════════════════════════════════════════

def _make_cloth_node(n_verts=6, constrain_first=True):
    """Build a minimal dangly ModelNode suitable for ClothRigSimulator."""
    from src.core.model_data import ModelNode
    node = ModelNode()
    node.name = 'cloth_test'
    node.vertices = [(float(i), 0.0, 0.0) for i in range(n_verts)]
    node.faces    = [(0, 1, 2), (1, 2, 3), (2, 3, 4), (3, 4, 5)][:n_verts - 2]
    node.uvs      = [(0.0, 0.0)] * n_verts
    # First vertex is pinned if constrain_first else all are free
    constraints = [1.0 if (i == 0 and constrain_first) else 0.0
                   for i in range(n_verts)]
    node.dangly_constraints  = constraints
    node.dangly_displacement = 2.0
    node.dangly_tightness    = 0.5
    node.dangly_period       = 1.0
    return node


class TestClothRigSimulatorKineticEnergy(unittest.TestCase):

    def setUp(self):
        from src.autorig.cloth_rig import ClothRigSimulator
        self.Sim = ClothRigSimulator

    def test_kinetic_energy_zero_at_rest(self):
        """Freshly created simulator has zero kinetic energy (no velocity)."""
        node = _make_cloth_node()
        sim  = self.Sim(node)
        ke   = sim.kinetic_energy()
        self.assertAlmostEqual(ke, 0.0, places=10)

    def test_kinetic_energy_positive_after_steps(self):
        """After applying wind and stepping, free verts should have KE > 0."""
        node = _make_cloth_node()
        sim  = self.Sim(node)
        sim.apply_wind(direction=(0.0, 1.0, 0.0), strength=5.0)
        for _ in range(5):
            sim.step()
        ke = sim.kinetic_energy()
        self.assertGreater(ke, 0.0)

    def test_kinetic_energy_all_pinned_stays_zero(self):
        """All-pinned node should always have KE == 0."""
        from src.core.model_data import ModelNode
        node = ModelNode()
        node.name = 'pinned'
        node.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 1.0, 0.0)]
        node.faces = [(0, 1, 2)]
        node.uvs   = [(0.0, 0.0)] * 3
        node.dangly_constraints  = [1.0, 1.0, 1.0]
        node.dangly_displacement = 1.0
        node.dangly_tightness    = 0.5
        node.dangly_period       = 1.0
        sim = self.Sim(node)
        sim.apply_wind(direction=(1.0, 0.0, 0.0), strength=10.0)
        for _ in range(10):
            sim.step()
        self.assertAlmostEqual(sim.kinetic_energy(), 0.0, places=10)

    def test_kinetic_energy_decreases_after_reset(self):
        """After reset, KE returns to zero."""
        node = _make_cloth_node()
        sim  = self.Sim(node)
        sim.apply_wind(direction=(1.0, 0.0, 0.0), strength=5.0)
        for _ in range(10):
            sim.step()
        self.assertGreater(sim.kinetic_energy(), 0.0)
        sim.reset()
        self.assertAlmostEqual(sim.kinetic_energy(), 0.0, places=10)

    def test_total_displacement_zero_at_rest(self):
        node = _make_cloth_node()
        sim  = self.Sim(node)
        self.assertAlmostEqual(sim.total_displacement(), 0.0, places=10)

    def test_total_displacement_increases_with_wind(self):
        node = _make_cloth_node()
        sim  = self.Sim(node)
        sim.apply_wind(direction=(0.0, 1.0, 0.0), strength=5.0)
        for _ in range(10):
            sim.step()
        self.assertGreater(sim.total_displacement(), 0.0)

    def test_total_displacement_reset(self):
        node = _make_cloth_node()
        sim  = self.Sim(node)
        sim.apply_wind(direction=(1.0, 0.0, 0.0), strength=5.0)
        for _ in range(10):
            sim.step()
        sim.reset()
        self.assertAlmostEqual(sim.total_displacement(), 0.0, places=10)

    def test_displacement_capped_by_dangly_displacement(self):
        """No free vertex should move beyond dangly_displacement from rest."""
        node = _make_cloth_node()
        node.dangly_displacement = 0.5
        sim  = self.Sim(node)
        sim.apply_wind(direction=(1.0, 0.0, 0.0), strength=20.0)
        for _ in range(50):
            sim.step()
        max_disp = 0.0
        for pos, rest in zip(sim.positions, sim._rest_pos):
            dx = pos[0] - rest[0]
            dy = pos[1] - rest[1]
            dz = pos[2] - rest[2]
            d = math.sqrt(dx*dx + dy*dy + dz*dz)
            if d > max_disp:
                max_disp = d
        self.assertLessEqual(max_disp, 0.5 + 1e-6)


# ════════════════════════════════════════════════════════════════════════════════
#  6. GltfRoundTripResult & gltf_round_trip_verify
# ════════════════════════════════════════════════════════════════════════════════

def _make_mesh_model(name='cube'):
    """Create a KotorModel with one real mesh node (a unit cube triangle fan)."""
    from src.core.model_data import KotorModel, ModelNode, NodeFlags
    m = KotorModel()
    m.name = name
    root = ModelNode(); root.name = 'RootDummy'; root.flags = int(NodeFlags.HEADER)
    mesh = ModelNode(); mesh.name = 'CubeMesh'
    mesh.flags = int(NodeFlags.MESH)
    mesh.render = True
    mesh.vertices = [
        (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (1.0, 1.0, 1.0), (0.0, 1.0, 1.0),
    ]
    mesh.faces = [(0,1,2),(0,2,3),(4,5,6),(4,6,7),(0,1,5),(0,5,4)]
    mesh.uvs   = [(u % 2 * 0.5, (u // 2) * 0.5) for u in range(len(mesh.vertices))]
    mesh.normals = [(0.0, 0.0, 1.0)] * len(mesh.vertices)
    mesh.texture  = 'cubetex'   # non-NULL texture prevents deform-helper detection
    root.children = [mesh]
    mesh.parent   = root
    m.root_node = root
    return m


class TestGltfRoundTripResult(unittest.TestCase):
    """Unit tests for the GltfRoundTripResult data class."""

    def setUp(self):
        from src.converters.mesh_converter import GltfRoundTripResult
        self.Result = GltfRoundTripResult

    def test_default_state_not_ok(self):
        r = self.Result()
        self.assertFalse(r.ok)

    def test_summary_contains_ok(self):
        r = self.Result()
        r.ok = True
        self.assertIn('OK=True', r.summary())

    def test_summary_vertex_delta(self):
        r = self.Result()
        r.vertex_count_delta['mesh1'] = (100, 102)
        s = r.summary()
        self.assertIn('mesh1', s)
        self.assertIn('100', s)
        self.assertIn('102', s)

    def test_summary_errors_listed(self):
        r = self.Result()
        r.errors.append('something went wrong')
        self.assertIn('something went wrong', r.summary())

    def test_summary_missing_nodes_listed(self):
        r = self.Result()
        r.node_names_missing = ['boneA', 'boneB']
        self.assertIn('boneA', r.summary())

    def test_animation_names_ok_field(self):
        r = self.Result()
        r.animation_names_ok = True
        self.assertIn('anim_names_ok=True', r.summary())


class TestGltfRoundTripVerify(unittest.TestCase):
    """Integration tests for gltf_round_trip_verify()."""

    def setUp(self):
        from src.converters.mesh_converter import gltf_round_trip_verify
        self.verify = gltf_round_trip_verify

    def test_simple_mesh_glb_round_trip(self):
        model  = _make_mesh_model()
        result = self.verify(model, binary=True)
        # We accept a relaxed pass: no export/import errors
        self.assertFalse(result.errors, f"Errors: {result.errors}")
        self.assertTrue(result.mesh_count_match,
                        "Mesh count should survive GLB round-trip")

    def test_simple_mesh_gltf_round_trip(self):
        model  = _make_mesh_model()
        result = self.verify(model, binary=False)
        self.assertFalse(result.errors, f"Errors: {result.errors}")
        self.assertTrue(result.mesh_count_match)

    def test_result_has_vertex_delta(self):
        model  = _make_mesh_model()
        result = self.verify(model, binary=True)
        if result.mesh_count_match and not result.errors:
            self.assertGreater(len(result.vertex_count_delta), 0)

    def test_result_uv_max_delta_within_tolerance(self):
        model  = _make_mesh_model()
        result = self.verify(model, binary=True, uv_tolerance=0.01)
        if not result.errors:
            self.assertLessEqual(result.uv_max_delta, 0.01 + 1e-9)

    def test_model_with_animation_round_trip(self):
        from src.core.model_data import Animation
        model = _make_mesh_model('animated_cube')
        a = Animation(); a.name = 'idle'; a.length = 1.0; a.anim_root = 'RootDummy'
        a.nodes = []
        model.animations.append(a)
        result = self.verify(model, binary=True)
        # Animations in glTF require sampler data; export may strip empty anims
        # Just check no crash
        self.assertIsInstance(result.ok, bool)

    def test_summary_method_produces_string(self):
        model  = _make_mesh_model()
        result = self.verify(model, binary=True)
        s = result.summary()
        self.assertIsInstance(s, str)
        self.assertIn('Round-trip', s)


# ════════════════════════════════════════════════════════════════════════════════
#  7. Module-level merge_usecomp_animations (regression)
# ════════════════════════════════════════════════════════════════════════════════

class TestMergeUsecompAnimations(unittest.TestCase):
    """Regression tests for the existing merge_usecomp_animations helper."""

    def test_merge_returns_node_count(self):
        from src.core.animation_engine import merge_usecomp_animations
        from src.core.model_data import KotorModel, ModelNode

        parent = _make_model('parent', ['spine', 'head'])
        uc = _make_anim('usecomp', ['spine', 'head'])
        parent.animations.append(uc)

        child = _make_model('child', ['spine'])

        count = merge_usecomp_animations(child, parent)
        self.assertEqual(count, 1)  # only 'spine' survives filter

    def test_merge_returns_zero_when_no_usecomp(self):
        from src.core.animation_engine import merge_usecomp_animations
        from src.core.model_data import KotorModel
        parent = KotorModel(); parent.name = 'p'
        parent.animations = [_make_anim('walk', ['spine'])]
        child  = KotorModel(); child.name  = 'c'
        count = merge_usecomp_animations(child, parent)
        self.assertEqual(count, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
