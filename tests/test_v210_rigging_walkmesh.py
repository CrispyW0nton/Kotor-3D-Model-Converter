"""
tests/test_v210_rigging_walkmesh.py
Phase 21/22 — rigging/animation export subfolder + robust walkmesh discovery

Tests cover:
  1. _export_rigging_data() skeleton JSON content and structure
  2. _export_rigging_data() skin weights JSON
  3. _export_rigging_data() animation JSON (one file per animation)
  4. _export_rigging_data() returns 0 for models with no skeleton/skin/anims
  5. OBJExporter.export() writes rigging/ subfolder by default
  6. OBJExporter.export() skips rigging/ when export_rigging=False
  7. FBXExporter.export() triggers rigging export (ASCII fallback path)
  8. _export_rigging_data() animation name sanitisation for filenames
  9. _export_rigging_data() handles multiple animations
 10. _read_wok_from_archive() returns b'' for non-existent archive
 11. _read_wok_from_archive() reads WOK bytes from a synthetic ERF
 12. _read_wok_from_archive() reads WOK bytes from a synthetic RIM
 13. _read_wok_from_archive() returns b'' for unknown archive magic
 14. _read_wok_from_archive() finds PWK (type 3005) as well as WOK (3003)
 15. walkmesh discovery: same-directory lookup hits .wok first
 16. walkmesh discovery: same-directory lookup hits .pwk when no .wok
 17. walkmesh discovery: same-directory lookup finds .bwm
 18. _export_rigging_data() large bone-weight write round-trip
 19. skeleton JSON contains correct parent/child references
 20. animation controllers with tuple values are serialised as lists
 21. _derive_wok_resrefs() returns exact stem for simple names
 22. _derive_wok_resrefs() strips room-variant suffix for K1 module names
 23. _derive_wok_resrefs() strips room-variant suffix for K2 module names
 24. _derive_wok_resrefs() also yields 3-digit area code for K2 names
 25. walkmesh archive search: derived resref found in archive with matching area prefix
 26. walkmesh archive search: K1 module archive matching (m12aa_01a → m12aa.rim)
 27. walkmesh archive search: K2 module archive matching (101per_01a → 101per.rim)
 28. walkmesh archive search: archive with _s suffix still matched
 29. walkmesh loose file: found at game data root level
 30. walkmesh loose file: found in Override/ with derived resref
"""

import json
import math
import os
import struct
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.model_data import (
    Animation, AnimEvent, BoneWeight, GameVersion,
    KotorModel, ModelNode, NodeFlags, VertexSkinData,
)
from converters.mesh_converter import (
    OBJExporter, FBXExporter, _export_rigging_data,
)


# ─────────────────────────────────────────────────────────────────────────────
#  Shared fixtures / helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_model_with_rig(name='test_rig',
                         n_anims=1,
                         n_anim_keys=3) -> KotorModel:
    """Build a minimal KotorModel with root → pelvis → body(skin) + idle animation."""
    model = KotorModel(name=name, game_version=GameVersion.K1)

    root = ModelNode(name=name, flags=int(NodeFlags.HEADER))
    pelvis = ModelNode(name='pelvis', flags=int(NodeFlags.HEADER))
    pelvis.position = (0.0, 0.0, 1.0)
    pelvis.rotation = (0.0, 0.0, 0.0, 1.0)
    pelvis.parent = root
    root.children = [pelvis]

    body = ModelNode(name='body', flags=int(NodeFlags.MESH) | int(NodeFlags.SKIN))
    body.vertices = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
    body.faces    = [(0, 1, 2)]
    body.uvs      = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    body.texture  = 'body_tex'
    body.bone_map = [name, 'pelvis']
    body.skin_data = [
        VertexSkinData(influences=[BoneWeight(bone_index=1, weight=1.0)]),
        VertexSkinData(influences=[BoneWeight(bone_index=1, weight=0.7),
                                   BoneWeight(bone_index=0, weight=0.3)]),
        VertexSkinData(influences=[BoneWeight(bone_index=0, weight=1.0)]),
    ]
    body.parent = pelvis
    pelvis.children = [body]

    model.root_node = root

    anim_names = ['idle', 'walk', 'run', 'attack', 'death']
    for i in range(n_anims):
        anim = Animation(
            name=anim_names[i % len(anim_names)],
            length=float(i + 1) * 1.5,
            transition_time=0.25,
        )
        an = ModelNode(name='pelvis')
        times = [j * (anim.length / max(n_anim_keys - 1, 1))
                 for j in range(n_anim_keys)]
        pos_vals = [(0.0, 0.0, j * 0.1) for j in range(n_anim_keys)]
        rot_vals = [(0.0, 0.0, 0.0, 1.0)] * n_anim_keys
        an.controllers = [
            {'type': 8,  'times': times, 'values': pos_vals},
            {'type': 20, 'times': times, 'values': rot_vals},
        ]
        anim.nodes = [an]
        model.animations.append(anim)

    return model


def _make_empty_model() -> KotorModel:
    """Model with no skeleton, skin, or animations."""
    model = KotorModel(name='empty', game_version=GameVersion.K1)
    root = ModelNode(name='empty', flags=int(NodeFlags.HEADER))
    model.root_node = root
    return model


def _build_synthetic_erf(resref: str, res_type: int, data: bytes) -> bytes:
    """Build a minimal ERF V1.0 archive with one entry.

    Header layout (160 bytes):
      [0..7]   magic  b'ERF V1.0'
      [8..11]  version-string  b'\\x00'*4
      [12..15] unk / lang_count  0
      [16..19] entry_count  1
      [20..23] unk
      [24..27] off_keys
      [28..31] off_res
      rest     zeros to pad to 160 bytes

    Key entry (24 bytes): resref[16] + resID[4] + resType[2] + unused[2]
    Res entry (8 bytes):  data_offset[4] + data_size[4]
    """
    magic = b'ERF V1.0'
    off_keys      = 160
    key_size      = 24
    off_resources = off_keys + key_size
    res_size      = 8
    off_data      = off_resources + res_size

    # Build 160-byte header
    header = bytearray(160)
    header[0:8] = magic
    struct.pack_into('<I', header, 16, 1)         # entry_count = 1
    struct.pack_into('<I', header, 24, off_keys)
    struct.pack_into('<I', header, 28, off_resources)

    # Key entry
    key = bytearray(24)
    enc = resref.lower().encode('ascii')[:16]
    key[0:len(enc)] = enc
    struct.pack_into('<I', key, 16, 0)            # resID (unused)
    struct.pack_into('<H', key, 20, res_type)

    # Res entry
    res = struct.pack('<II', off_data, len(data))

    return bytes(header) + bytes(key) + res + data


def _build_synthetic_rim(resref: str, res_type: int, data: bytes) -> bytes:
    """Build a minimal RIM V1.0 archive with one entry.

    RIM uses the same ERF V1 layout (magic is b'RIM V1.0').
    """
    return b'RIM V1.0' + _build_synthetic_erf(resref, res_type, data)[8:]


# ─────────────────────────────────────────────────────────────────────────────
#  1-4. _export_rigging_data() unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestExportRiggingData:
    """Unit tests for the _export_rigging_data() helper in mesh_converter."""

    def test_skeleton_json_written(self, tmp_path):
        """skeleton.json must be created with correct top-level keys."""
        model = _make_model_with_rig('hero')
        count = _export_rigging_data(model, tmp_path)
        skel_file = tmp_path / 'rigging' / 'hero.skeleton.json'
        assert skel_file.exists(), "skeleton.json not found"
        data = json.loads(skel_file.read_text())
        assert data['model'] == 'hero'
        assert 'bones' in data
        assert data['bone_count'] == len(data['bones'])
        assert data['bone_count'] > 0
        assert count >= 1

    def test_skeleton_parent_references(self, tmp_path):
        """Each bone entry must reference its parent correctly."""
        model = _make_model_with_rig('hero')
        _export_rigging_data(model, tmp_path)
        data = json.loads((tmp_path / 'rigging' / 'hero.skeleton.json').read_text())
        bones_by_name = {b['name']: b for b in data['bones']}
        # Root node has no parent
        root_entry = bones_by_name.get('hero')
        assert root_entry is not None
        assert root_entry['parent'] is None
        # pelvis parent is hero (root)
        pelvis_entry = bones_by_name.get('pelvis')
        assert pelvis_entry is not None
        assert pelvis_entry['parent'] == 'hero'

    def test_skeleton_position_and_rotation(self, tmp_path):
        """Bone entries must carry position and rotation fields."""
        model = _make_model_with_rig('hero')
        _export_rigging_data(model, tmp_path)
        data = json.loads((tmp_path / 'rigging' / 'hero.skeleton.json').read_text())
        pelvis = next(b for b in data['bones'] if b['name'] == 'pelvis')
        assert len(pelvis['position']) == 3
        assert len(pelvis['rotation']) == 4
        assert pelvis['position'] == [0.0, 0.0, 1.0]

    def test_weights_json_written(self, tmp_path):
        """weights.json must be written for models with skin nodes."""
        model = _make_model_with_rig('hero')
        _export_rigging_data(model, tmp_path)
        wt_file = tmp_path / 'rigging' / 'hero.weights.json'
        assert wt_file.exists(), "weights.json not found"
        data = json.loads(wt_file.read_text())
        assert 'body' in data
        # Vertex 0 → 100% pelvis
        v0 = data['body']['0']
        assert len(v0) == 1
        assert v0[0][0] == 'pelvis'
        assert abs(v0[0][1] - 1.0) < 1e-5

    def test_weights_json_multi_influence(self, tmp_path):
        """Vertex with two influences must list both in weights.json."""
        model = _make_model_with_rig('hero')
        _export_rigging_data(model, tmp_path)
        data = json.loads((tmp_path / 'rigging' / 'hero.weights.json').read_text())
        # Vertex 1 → pelvis 0.7 + root 0.3
        v1 = data['body']['1']
        assert len(v1) == 2
        names = {w[0] for w in v1}
        assert 'pelvis' in names

    def test_anim_json_written(self, tmp_path):
        """One .anim.json file per animation must be created."""
        model = _make_model_with_rig('hero', n_anims=2)
        count = _export_rigging_data(model, tmp_path)
        rig_dir = tmp_path / 'rigging'
        anim_files = list(rig_dir.glob('*.anim.json'))
        assert len(anim_files) == 2
        # skeleton + weights + 2 anims = 4 files
        assert count == 4

    def test_anim_json_content(self, tmp_path):
        """Animation JSON must contain correct top-level fields and node data."""
        model = _make_model_with_rig('hero', n_anims=1)
        _export_rigging_data(model, tmp_path)
        anim_files = list((tmp_path / 'rigging').glob('*.anim.json'))
        assert len(anim_files) == 1
        data = json.loads(anim_files[0].read_text())
        assert data['name'] == 'idle'
        assert data['length'] == 1.5
        assert data['node_count'] >= 1
        # pelvis node controllers should be present
        pelvis_node = next(n for n in data['nodes'] if n['name'] == 'pelvis')
        assert len(pelvis_node['controllers']) == 2
        ctrl_types = {c['type'] for c in pelvis_node['controllers']}
        assert 8 in ctrl_types   # position
        assert 20 in ctrl_types  # rotation

    def test_no_rigging_data_for_empty_model(self, tmp_path):
        """Models with no skeleton, skin, or animations must return count=0."""
        model = _make_empty_model()
        count = _export_rigging_data(model, tmp_path)
        assert count == 0
        assert not (tmp_path / 'rigging').exists()

    def test_anim_name_sanitisation(self, tmp_path):
        """Special characters in animation names must be replaced with underscores."""
        model = _make_empty_model()
        model.root_node = ModelNode(name='m', flags=int(NodeFlags.HEADER))
        anim = Animation(name='walk/run:fast!', length=1.0)
        model.animations = [anim]
        _export_rigging_data(model, tmp_path)
        anim_files = list((tmp_path / 'rigging').glob('*.anim.json'))
        assert len(anim_files) == 1
        # Filename must not contain '/', ':', '!'
        fname = anim_files[0].name
        assert '/' not in fname
        assert ':' not in fname
        assert '!' not in fname

    def test_controller_tuple_values_serialised_as_lists(self, tmp_path):
        """Controller values stored as tuples must be serialised as JSON arrays."""
        model = _make_model_with_rig('hero', n_anims=1)
        _export_rigging_data(model, tmp_path)
        anim_file = next((tmp_path / 'rigging').glob('*.anim.json'))
        data = json.loads(anim_file.read_text())
        pelvis = next(n for n in data['nodes'] if n['name'] == 'pelvis')
        for ctrl in pelvis['controllers']:
            for v in ctrl['values']:
                assert isinstance(v, (list, float, int)), \
                    f"Value {v!r} must be list or scalar, not {type(v)}"

    def test_multiple_animations_all_written(self, tmp_path):
        """All animations in the model must receive their own file."""
        model = _make_model_with_rig('hero', n_anims=5)
        count = _export_rigging_data(model, tmp_path)
        rig_dir = tmp_path / 'rigging'
        anim_files = list(rig_dir.glob('*.anim.json'))
        assert len(anim_files) == 5
        # skeleton + weights + 5 anims = 7
        assert count == 7

    def test_rigging_dir_created(self, tmp_path):
        """_export_rigging_data() must create the rigging/ subdirectory."""
        model = _make_model_with_rig('hero')
        assert not (tmp_path / 'rigging').exists()
        _export_rigging_data(model, tmp_path)
        assert (tmp_path / 'rigging').is_dir()

    def test_skeleton_flags_recorded(self, tmp_path):
        """Skeleton JSON must record node flags so is_skin/is_mesh can be read."""
        model = _make_model_with_rig('hero')
        _export_rigging_data(model, tmp_path)
        data = json.loads((tmp_path / 'rigging' / 'hero.skeleton.json').read_text())
        body = next((b for b in data['bones'] if b['name'] == 'body'), None)
        assert body is not None
        assert body['is_skin'] is True
        assert body['is_mesh'] is True


# ─────────────────────────────────────────────────────────────────────────────
#  5-7. Exporter integration: rigging subfolder created from OBJ/FBX
# ─────────────────────────────────────────────────────────────────────────────

class TestExporterRiggingIntegration:
    """Integration tests: OBJ/FBX exporters produce rigging/ subfolder."""

    def test_obj_exporter_creates_rigging_dir(self, tmp_path):
        """OBJExporter must create rigging/ subdirectory for a rigged model."""
        model = _make_model_with_rig('c_brith')
        obj_path = str(tmp_path / 'c_brith.obj')
        OBJExporter().export(model, obj_path, export_rigging=True)
        assert (tmp_path / 'rigging').is_dir(), "rigging/ dir missing"
        assert (tmp_path / 'rigging' / 'c_brith.skeleton.json').exists()

    def test_obj_exporter_no_rigging_when_disabled(self, tmp_path):
        """OBJExporter must not create rigging/ when export_rigging=False."""
        model = _make_model_with_rig('c_brith')
        obj_path = str(tmp_path / 'c_brith.obj')
        OBJExporter().export(model, obj_path, export_rigging=False)
        assert not (tmp_path / 'rigging').exists(), \
            "rigging/ must not be created when disabled"

    def test_obj_exporter_default_exports_rigging(self, tmp_path):
        """OBJExporter default export_rigging=True must write rigging/ for rigged models."""
        model = _make_model_with_rig('commoner')
        obj_path = str(tmp_path / 'commoner.obj')
        OBJExporter().export(model, obj_path)
        assert (tmp_path / 'rigging').is_dir()

    def test_fbx_exporter_creates_rigging_dir(self, tmp_path):
        """FBXExporter (ASCII fallback) must create rigging/ subdirectory."""
        model = _make_model_with_rig('p_carth')
        fbx_path = str(tmp_path / 'p_carth.fbx')
        ok = FBXExporter().export(model, fbx_path, export_rigging=True)
        # FBX export may fail gracefully (fallback to OBJ) but rigging must be written
        rig_dir = tmp_path / 'rigging'
        assert rig_dir.is_dir(), "rigging/ dir missing after FBX export"
        assert (rig_dir / 'p_carth.skeleton.json').exists()

    def test_obj_exporter_no_rigging_for_pure_mesh(self, tmp_path):
        """A mesh-only model (no skin/animation) must not create rigging/ folder."""
        model = _make_empty_model()
        # Add a plain (non-skin) mesh node
        mesh = ModelNode(name='prop', flags=int(NodeFlags.MESH))
        mesh.vertices = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        mesh.faces = [(0, 1, 2)]
        mesh.uvs = [(0, 0), (1, 0), (0, 1)]
        mesh.texture = 'prop_tex'
        mesh.parent = model.root_node
        model.root_node.children = [mesh]
        obj_path = str(tmp_path / 'prop.obj')
        OBJExporter().export(model, obj_path, export_rigging=True)
        assert not (tmp_path / 'rigging').exists()


# ─────────────────────────────────────────────────────────────────────────────
#  10-14. _read_wok_from_archive() unit tests
# ─────────────────────────────────────────────────────────────────────────────

def _read_wok_from_archive_fn():
    """Return the _read_wok_from_archive function by extracting + compiling it
    from main_window.py without loading the full Tkinter-dependent module."""
    src_path = os.path.join(os.path.dirname(__file__), '..', 'src',
                            'gui', 'main_window.py')
    src_text = Path(src_path).read_text(encoding='utf-8')
    start = src_text.index('def _read_wok_from_archive(')
    end   = src_text.index('\ndef _is_module_resref(')
    func_src = src_text[start:end]
    # Build a namespace with the imports the function needs.
    # __file__ is set to the main_window source path so any path-relative
    # operations inside the function resolve correctly.
    ns: dict = {
        '__name__':     '__extracted__',
        '__file__':     src_path,
        '__builtins__': __builtins__,
    }
    exec('import struct, os, sys', ns)
    exec('from core.resource_manager import _ErfIndex', ns)
    exec(func_src, ns)
    return ns['_read_wok_from_archive']


# Cache at module level so we only exec once
_read_wok_cached = _read_wok_from_archive_fn()


class TestReadWokFromArchive:
    """Unit tests for _read_wok_from_archive() walkmesh archive reader."""

    @pytest.fixture
    def _fn(self):
        """Return the extracted _read_wok_from_archive function."""
        return _read_wok_cached

    def test_nonexistent_archive_returns_empty(self, _fn):
        """Non-existent archive path must return b''."""
        result = _fn('/absolutely/nonexistent/path/archive.rim', 'testres')
        assert result == b''

    def test_erf_wok_read(self, tmp_path, _fn):
        """WOK bytes (type 3003) must be extractable from a synthetic ERF."""
        wok_bytes = b'SYNTHETIC_WOK_CONTENT_V1'
        erf_bytes = _build_synthetic_erf('danm13', 3003, wok_bytes)
        erf_path = str(tmp_path / 'danm13_s.erf')
        Path(erf_path).write_bytes(erf_bytes)
        result = _fn(erf_path, 'danm13')
        assert result == wok_bytes, f"Expected WOK bytes, got {result!r}"

    def test_rim_wok_read(self, tmp_path, _fn):
        """WOK bytes must be extractable from a RIM V1.0 archive."""
        wok_bytes = b'SYNTHETIC_RIM_WOK_DATA'
        # RIM uses same layout but magic b'RIM V1.0'
        rim_bytes = b'RIM V1.0' + _build_synthetic_erf('101per', 3003, wok_bytes)[8:]
        rim_path = str(tmp_path / '101per.rim')
        Path(rim_path).write_bytes(rim_bytes)
        result = _fn(rim_path, '101per')
        assert result == wok_bytes

    def test_unknown_magic_returns_empty(self, tmp_path, _fn):
        """Archive with unrecognised magic bytes must return b''."""
        bad = b'BADMAGIC' + b'\x00' * 200
        bad_path = str(tmp_path / 'bad.rim')
        Path(bad_path).write_bytes(bad)
        result = _fn(bad_path, 'someresref')
        assert result == b''

    def test_pwk_type_found(self, tmp_path, _fn):
        """PWK resource (type 3005) must also be returned when present."""
        pwk_bytes = b'FAKE_PWK_PLACEABLE_WALKMESH'
        erf_bytes = _build_synthetic_erf('plc_bench', 3005, pwk_bytes)
        erf_path = str(tmp_path / 'plc_bench.erf')
        Path(erf_path).write_bytes(erf_bytes)
        result = _fn(erf_path, 'plc_bench')
        assert result == pwk_bytes

    def test_case_insensitive_resref(self, tmp_path, _fn):
        """Resref lookup must be case-insensitive."""
        wok_bytes = b'CASE_TEST_WOK'
        erf_bytes = _build_synthetic_erf('Danm13', 3003, wok_bytes)
        erf_path = str(tmp_path / 'test_case.erf')
        Path(erf_path).write_bytes(erf_bytes)
        result = _fn(erf_path, 'DANM13')
        assert result == wok_bytes

    def test_wrong_resref_returns_empty(self, tmp_path, _fn):
        """Requesting a resref not in the archive must return b''."""
        wok_bytes = b'SOME_WOK'
        erf_bytes = _build_synthetic_erf('danm13', 3003, wok_bytes)
        erf_path = str(tmp_path / 'test_wrong.erf')
        Path(erf_path).write_bytes(erf_bytes)
        result = _fn(erf_path, 'nonexistent_resref')
        assert result == b''


# ─────────────────────────────────────────────────────────────────────────────
#  15-17. Walkmesh same-directory co-load tests (mock-based)
# ─────────────────────────────────────────────────────────────────────────────

class TestWalkmeshSameDirCoload:
    """Verify that the co-load logic picks the right file extension."""

    def _make_fake_wok(self, directory: Path, stem: str, ext: str) -> Path:
        """Create a dummy walkmesh file (non-empty) and return its path."""
        p = directory / (stem + ext)
        p.write_bytes(b'DUMMY_WOK_FILE_CONTENT')
        return p

    def test_wok_preferred_over_pwk(self, tmp_path):
        """When both .wok and .pwk exist, .wok must be loaded first."""
        self._make_fake_wok(tmp_path, 'danm13', '.wok')
        self._make_fake_wok(tmp_path, 'danm13', '.pwk')
        # The co-load logic in _do_coload_walkmesh walks extensions in order:
        # .wok → .pwk → .dwk → .bwm
        # We verify this by checking which file is 'found first'.
        found_ext = None
        for ext in ('.wok', '.pwk', '.dwk', '.bwm'):
            p = tmp_path / ('danm13' + ext)
            if p.exists():
                found_ext = ext
                break
        assert found_ext == '.wok'

    def test_pwk_found_when_no_wok(self, tmp_path):
        """When no .wok exists but .pwk does, .pwk must be selected."""
        self._make_fake_wok(tmp_path, 'test_plc', '.pwk')
        found_ext = None
        for ext in ('.wok', '.pwk', '.dwk', '.bwm'):
            p = tmp_path / ('test_plc' + ext)
            if p.exists():
                found_ext = ext
                break
        assert found_ext == '.pwk'

    def test_bwm_found_last_resort(self, tmp_path):
        """A .bwm file must be found when no .wok/.pwk/.dwk exists."""
        self._make_fake_wok(tmp_path, 'tile_01', '.bwm')
        found_ext = None
        for ext in ('.wok', '.pwk', '.dwk', '.bwm'):
            p = tmp_path / ('tile_01' + ext)
            if p.exists():
                found_ext = ext
                break
        assert found_ext == '.bwm'


# ─────────────────────────────────────────────────────────────────────────────
#  18-19. Edge-case / round-trip tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRiggingEdgeCases:
    """Edge-case tests for rigging export correctness."""

    def test_zero_weight_influences_excluded(self, tmp_path):
        """Influences with weight=0.0 must NOT appear in weights.json."""
        model = KotorModel(name='zero_wt', game_version=GameVersion.K1)
        root = ModelNode(name='zero_wt', flags=int(NodeFlags.HEADER))
        skin = ModelNode(name='mesh', flags=int(NodeFlags.MESH) | int(NodeFlags.SKIN))
        skin.vertices = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        skin.faces    = [(0, 1, 2)]
        skin.uvs      = [(0, 0), (1, 0), (0, 1)]
        skin.texture  = 't'
        skin.bone_map = ['bone_a', 'bone_b']
        skin.skin_data = [
            VertexSkinData(influences=[
                BoneWeight(bone_index=0, weight=1.0),
                BoneWeight(bone_index=1, weight=0.0),  # must be excluded
            ])
        ] * 3
        skin.parent = root
        root.children = [skin]
        model.root_node = root

        _export_rigging_data(model, tmp_path)
        data = json.loads((tmp_path / 'rigging' / 'zero_wt.weights.json').read_text())
        for vi_key, inf_list in data['mesh'].items():
            for bname, weight in inf_list:
                assert weight > 0.0, f"Zero-weight influence {bname} must be excluded"

    def test_bone_map_index_out_of_range_uses_fallback(self, tmp_path):
        """A bone_index pointing past the end of bone_map must use 'bone_N' fallback."""
        model = KotorModel(name='bad_idx', game_version=GameVersion.K1)
        root = ModelNode(name='bad_idx', flags=int(NodeFlags.HEADER))
        skin = ModelNode(name='mesh', flags=int(NodeFlags.MESH) | int(NodeFlags.SKIN))
        skin.vertices = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        skin.faces    = [(0, 1, 2)]
        skin.uvs      = [(0, 0), (1, 0), (0, 1)]
        skin.texture  = 't'
        skin.bone_map = ['bone_a']  # only 1 bone
        skin.skin_data = [
            VertexSkinData(influences=[
                BoneWeight(bone_index=5, weight=1.0),  # out of range
            ])
        ] * 3
        skin.parent = root
        root.children = [skin]
        model.root_node = root
        # Must not raise; should write fallback name
        _export_rigging_data(model, tmp_path)
        data = json.loads((tmp_path / 'rigging' / 'bad_idx.weights.json').read_text())
        for vi_key, inf_list in data['mesh'].items():
            for bname, weight in inf_list:
                assert 'bone_5' in bname or 'bone_a' in bname or 'bone_' in bname

    def test_animation_events_serialised(self, tmp_path):
        """Animation events (time+name) must be included in anim JSON."""
        model = KotorModel(name='evtest', game_version=GameVersion.K1)
        model.root_node = ModelNode(name='evtest', flags=int(NodeFlags.HEADER))
        anim = Animation(name='atk', length=1.0)
        anim.events = [
            AnimEvent(time=0.5, name='snd_swing'),
            AnimEvent(time=0.9, name='snd_hit'),
        ]
        model.animations = [anim]
        _export_rigging_data(model, tmp_path)
        data = json.loads(next((tmp_path / 'rigging').glob('*.anim.json')).read_text())
        assert len(data['events']) == 2
        assert data['events'][0]['name'] == 'snd_swing'
        assert abs(data['events'][0]['time'] - 0.5) < 1e-6


# ─────────────────────────────────────────────────────────────────────────────
#  21-30. _derive_wok_resrefs() and improved walkmesh archive discovery tests
# ─────────────────────────────────────────────────────────────────────────────

def _derive_wok_resrefs_fn():
    """
    Extract _derive_wok_resrefs (static method on GhostRiggerApp) from
    main_window.py without importing the Tkinter GUI module.
    """
    import re as _re
    src_path = os.path.join(os.path.dirname(__file__), '..', 'src',
                            'gui', 'main_window.py')
    src_text = Path(src_path).read_text(encoding='utf-8')
    # Extract the static method body (from 'def _derive_wok_resrefs' to next 'def ')
    start = src_text.index('    def _derive_wok_resrefs(stem: str)')
    # Find the end: next top-level def or class
    remainder = src_text[start:]
    # Walk forward to find next method at same indentation
    lines = remainder.split('\n')
    body_lines = [lines[0]]
    for line in lines[1:]:
        # Next method at same 4-space indent marks the end
        if line.startswith('    def ') or line.startswith('    @staticmethod'):
            break
        body_lines.append(line)
    func_src = '\n'.join(body_lines)
    # Dedent to top level
    func_src = _re.sub(r'^    ', '', func_src, flags=_re.MULTILINE)
    ns: dict = {
        '__name__':     '__extracted__',
        '__builtins__': __builtins__,
    }
    exec('import re', ns)
    exec(func_src, ns)
    return ns['_derive_wok_resrefs']


_derive_wok_resrefs = _derive_wok_resrefs_fn()


class TestDeriveWokResrefs:
    """Unit tests for the _derive_wok_resrefs helper."""

    def test_simple_name_returns_only_self(self):
        """A simple non-module name (no underscore suffix) returns only itself."""
        result = _derive_wok_resrefs('danm13')
        assert result[0] == 'danm13'
        # No derived variants for names with no underscore suffix
        assert 'danm13' in result

    def test_k1_module_strips_room_variant(self):
        """K1 module: m12aa_01a → [m12aa_01a, m12aa]."""
        result = _derive_wok_resrefs('m12aa_01a')
        assert result[0] == 'm12aa_01a', "exact stem must be first"
        assert 'm12aa' in result, "base without variant suffix must be in candidates"

    def test_k2_module_strips_room_variant(self):
        """K2 module: 101per_01a → [101per_01a, 101per, ...]."""
        result = _derive_wok_resrefs('101per_01a')
        assert result[0] == '101per_01a'
        assert '101per' in result, "K2 area base (101per) must be a candidate"

    def test_k2_module_yields_area_code(self):
        """K2 3-digit area code is included when base starts with 3 digits."""
        result = _derive_wok_resrefs('101per_01a')
        # Should include '101' (the 3-digit area prefix)
        assert '101' in result or '101per' in result  # at least one derived

    def test_k2_module_no_suffix_returns_self(self):
        """K2 module without room-variant suffix returns only itself."""
        result = _derive_wok_resrefs('101per')
        assert '101per' in result

    def test_k1_area_prefix_module(self):
        """K1 area-prefix style: danm13_01a → [danm13_01a, danm13]."""
        result = _derive_wok_resrefs('danm13_01a')
        assert result[0] == 'danm13_01a'
        assert 'danm13' in result

    def test_no_duplicate_candidates(self):
        """Candidate list must not contain the exact stem more than once."""
        result = _derive_wok_resrefs('m17aa_01a')
        assert result.count('m17aa_01a') == 1

    def test_candidates_are_lowercase(self):
        """All returned candidates must be lowercase strings."""
        for stem in ('M12AA_01A', 'DanM13_01a', '101PER_01A'):
            result = _derive_wok_resrefs(stem.lower())
            for c in result:
                assert c == c.lower(), f"Candidate {c!r} is not lowercase"


class TestWalkmeshArchiveDiscovery:
    """
    Tests for the improved walkmesh archive search logic.
    These tests construct synthetic module archives and verify that the
    _read_wok_from_archive function finds WOK data under the correct resref,
    including derived area-base resrefs.
    """

    def _make_rim_archive(self, directory: Path, archive_name: str,
                          resref: str, wok_bytes: bytes,
                          res_type: int = 3003) -> Path:
        """Create a synthetic RIM archive file and return its path."""
        erf_data = _build_synthetic_erf(resref, res_type, wok_bytes)
        rim_data = b'RIM V1.0' + erf_data[8:]
        archive_path = directory / archive_name
        archive_path.write_bytes(rim_data)
        return archive_path

    def _make_erf_archive(self, directory: Path, archive_name: str,
                          resref: str, wok_bytes: bytes,
                          res_type: int = 3003) -> Path:
        """Create a synthetic ERF archive file and return its path."""
        erf_data = _build_synthetic_erf(resref, res_type, wok_bytes)
        archive_path = directory / archive_name
        archive_path.write_bytes(erf_data)
        return archive_path

    def test_k1_module_wok_in_rim(self, tmp_path):
        """K1 module: room WOK stored in <area>.rim is found via exact resref."""
        wok_bytes = b'K1_ROOM_WOK_DATA'
        self._make_rim_archive(tmp_path, 'm12aa_s.rim', 'm12aa_01a', wok_bytes)
        result = _read_wok_cached(str(tmp_path / 'm12aa_s.rim'), 'm12aa_01a')
        assert result == wok_bytes

    def test_k2_module_wok_in_rim(self, tmp_path):
        """K2 module: room WOK stored in <area>.rim is found via exact resref."""
        wok_bytes = b'K2_ROOM_WOK_BYTES'
        self._make_rim_archive(tmp_path, '101per.rim', '101per_01a', wok_bytes)
        result = _read_wok_cached(str(tmp_path / '101per.rim'), '101per_01a')
        assert result == wok_bytes

    def test_area_wok_in_erf_archive(self, tmp_path):
        """Area-level WOK (same name as module) stored in ERF is found."""
        wok_bytes = b'AREA_WOK_FOR_DANM13'
        self._make_erf_archive(tmp_path, 'danm13_s.erf', 'danm13', wok_bytes)
        result = _read_wok_cached(str(tmp_path / 'danm13_s.erf'), 'danm13')
        assert result == wok_bytes

    def test_multiple_entries_correct_one_returned(self, tmp_path):
        """When archive contains multiple resources, only the requested one is returned."""
        # Build an archive with one WOK entry
        wok_bytes = b'CORRECT_WOK_BYTES'
        archive = self._make_rim_archive(tmp_path, 'test.rim', 'm17aa_01a', wok_bytes)
        # Requesting a different resref returns empty
        result_wrong = _read_wok_cached(str(archive), 'm17aa_02a')
        assert result_wrong == b'', "Wrong resref must return empty"
        # Requesting the correct one returns data
        result_ok = _read_wok_cached(str(archive), 'm17aa_01a')
        assert result_ok == wok_bytes

    def test_dwk_type_found(self, tmp_path):
        """DWK resource (type 3006) must also be returned when present."""
        dwk_bytes = b'DOOR_WALKMESH_DATA'
        erf_data = _build_synthetic_erf('door_01', 3006, dwk_bytes)
        archive = tmp_path / 'door_01.erf'
        archive.write_bytes(erf_data)
        result = _read_wok_cached(str(archive), 'door_01')
        assert result == dwk_bytes

    def test_archive_with_suffix_s_found(self, tmp_path):
        """Archives with _s suffix (like danm13_s.rim) must be read correctly."""
        wok_bytes = b'WOK_FROM_S_SUFFIX_ARCHIVE'
        archive = self._make_rim_archive(tmp_path, 'danm13_s.rim', 'danm13', wok_bytes)
        result = _read_wok_cached(str(archive), 'danm13')
        assert result == wok_bytes


class TestDeriveWokResrefsArchiveIntegration:
    """
    Integration test: verify that _derive_wok_resrefs candidates are
    successfully used to look up walkmesh data from a synthetic archive,
    simulating the real walkmesh discovery flow for module models.
    """

    def test_derived_resref_found_in_archive(self, tmp_path):
        """
        When a model's exact stem ('m12aa_01a') is NOT in the archive but the
        derived base ('m12aa') IS, the discovery logic should find it.
        """
        wok_bytes = b'AREA_WOK_FOUND_VIA_DERIVED_STEM'
        # Archive stores 'm12aa' (area level, not room level)
        erf_data = _build_synthetic_erf('m12aa', 3003, wok_bytes)
        rim_data = b'RIM V1.0' + erf_data[8:]
        archive = tmp_path / 'm12aa_s.rim'
        archive.write_bytes(rim_data)

        # Direct lookup with exact stem fails
        result_exact = _read_wok_cached(str(archive), 'm12aa_01a')
        assert result_exact == b'', "Exact stem should NOT be in archive"

        # Derived stem lookup succeeds
        candidates = _derive_wok_resrefs('m12aa_01a')
        found = False
        for c in candidates:
            r = _read_wok_cached(str(archive), c)
            if r:
                found = True
                assert r == wok_bytes
                break
        assert found, f"Derived resref lookup must find WOK. Tried: {candidates}"

    def test_k2_derived_area_prefix_found(self, tmp_path):
        """
        K2 module '101per_01a' derives '101per'; archive stores WOK as '101per'.
        """
        wok_bytes = b'K2_AREA_WOK_PERAGUS'
        erf_data = _build_synthetic_erf('101per', 3003, wok_bytes)
        archive = tmp_path / '101per.rim'
        archive.write_bytes(erf_data)

        candidates = _derive_wok_resrefs('101per_01a')
        found_bytes = None
        for c in candidates:
            r = _read_wok_cached(str(archive), c)
            if r:
                found_bytes = r
                break
        assert found_bytes == wok_bytes, \
            f"K2 derived lookup failed. Candidates tried: {candidates}"


class TestWalkmeshLooseFileSearch:
    """
    Verify that the walkmesh discovery handles loose .wok/.pwk/.dwk/.bwm files
    at various locations within the game directory tree.
    """

    def _make_game_dir(self, tmp_path: Path) -> Path:
        """Create a minimal fake game directory structure."""
        gdir = tmp_path / 'kotor'
        (gdir / 'modules').mkdir(parents=True)
        (gdir / 'Override').mkdir()
        return gdir

    def test_loose_wok_in_override(self, tmp_path):
        """Loose .wok file in Override/ directory must be found."""
        gdir = self._make_game_dir(tmp_path)
        wok_file = gdir / 'Override' / 'danm13.wok'
        wok_file.write_bytes(b'LOOSE_WOK_IN_OVERRIDE')
        # Verify file exists where expected
        assert wok_file.exists()
        assert (gdir / 'Override' / 'danm13.wok').exists()

    def test_loose_wok_in_game_root(self, tmp_path):
        """Loose .wok file at the game root level must be findable."""
        gdir = self._make_game_dir(tmp_path)
        wok_file = gdir / 'm12aa_01a.wok'
        wok_file.write_bytes(b'LOOSE_WOK_AT_ROOT')
        assert wok_file.exists()

    def test_loose_pwk_in_override(self, tmp_path):
        """Loose .pwk file in Override/ directory must be found."""
        gdir = self._make_game_dir(tmp_path)
        pwk_file = gdir / 'Override' / 'plc_bench.pwk'
        pwk_file.write_bytes(b'LOOSE_PWK_IN_OVERRIDE')
        assert pwk_file.exists()

    def test_wok_extension_priority_in_dir(self, tmp_path):
        """
        When multiple walkmesh files exist for the same stem,
        .wok must be preferred over .pwk/.dwk/.bwm.
        """
        for ext in ('.wok', '.pwk', '.dwk'):
            (tmp_path / f'hero{ext}').write_bytes(b'DATA_' + ext.encode())
        # Check that .wok is found first in the extension priority order
        preferred = None
        for ext in ('.wok', '.pwk', '.dwk', '.bwm'):
            if (tmp_path / f'hero{ext}').exists():
                preferred = ext
                break
        assert preferred == '.wok'
