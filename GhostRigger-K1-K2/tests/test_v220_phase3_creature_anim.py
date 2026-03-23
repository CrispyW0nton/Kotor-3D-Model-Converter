"""
test_v220_phase3_creature_anim.py
===================================
Phase 3 tests for GhostRigger-K1-K2:

  Phase 3.3  — UTC→Viewport pipeline (creature_appearance.build_creature_model,
                                       load_utc_into_viewport)
  Phase 3.4  — Animation controller improvements:
                  • Detonate controller (502) in mdl_parser CTRL_TYPE_NAMES
                  • No duplicate keys in CTRL_TYPE_NAMES dict
                  • Light Radius = 88 (KotOR.js-verified, not 80)
  Phase 3.7  — Supermodel animation inheritance (merge_supermodel_animations)

References
----------
  KotOR.js  OdysseyModelControllerType.ts  (Detonate=502, Radius=88, BirthRate=88)
  KotOR.js  OdysseyModel3D.SuperModelLoader lines 788-803  (copy parent anims)
  PyKotor   tools/creature.py              (body/head model resolution)
  xoreos    src/engines/kotor/creature.cpp (appearance chain)
"""

import struct
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ─────────────────────────────────────────────────────────────────────────────
#  Minimal stubs
# ─────────────────────────────────────────────────────────────────────────────

def _make_utc_gff(appearance_id: int = 0, good_evil: int = 50) -> bytes:
    """Build a minimal valid GFF V3.2 (.utc) binary with Appearance_Type + GoodEvil."""
    # GFF V3.2: 14-DWORD header (56 bytes)
    n_structs  = 1
    n_fields   = 2
    n_labels   = 2
    fdata_sz   = 0
    findx_sz   = 2 * 4   # 2 field indices, each uint32
    listindx_sz = 0

    struct_off  = 56
    field_off   = struct_off  + n_structs * 12
    label_off   = field_off   + n_fields  * 12
    fdata_off   = label_off   + n_labels  * 16
    findx_off   = fdata_off   + fdata_sz
    listindx_off = findx_off  + findx_sz

    hdr = struct.pack('<4s4s',   b'UTC ', b'V3.2')
    hdr += struct.pack('<12I',
        struct_off, n_structs,
        field_off,  n_fields,
        label_off,  n_labels,
        fdata_off,  fdata_sz,
        findx_off,  findx_sz,
        listindx_off, listindx_sz,
    )
    assert len(hdr) == 56

    # Struct 0: type=0xFFFFFFFF, data_offset=0 (index into field-indices array), field_count=2
    structs_bytes = struct.pack('<III', 0xFFFFFFFF, 0, 2)

    # Field 0: WORD (type=2) Appearance_Type = appearance_id
    # Field 1: BYTE (type=0) GoodEvil = good_evil
    f0 = struct.pack('<III', 2, 0, appearance_id)   # type=WORD, label_idx=0
    f1 = struct.pack('<III', 0, 1, good_evil)        # type=BYTE, label_idx=1
    fields_bytes = f0 + f1

    # Labels: 16 bytes each, null-padded
    def _label(s):
        b = s.encode('ascii')[:16]
        return b + b'\x00' * (16 - len(b))
    labels_bytes = _label('Appearance_Type') + _label('GoodEvil')

    # Field indices for struct 0: [0, 1]
    findx_bytes = struct.pack('<II', 0, 1)

    return hdr + structs_bytes + fields_bytes + labels_bytes + findx_bytes


def _make_appearance_2da(rows=None) -> bytes:
    """
    Build a minimal ASCII appearance.2da with given rows.
    Each row: (label, modeltype, modela, texa, race, supermodel, normalhead)
    """
    if rows is None:
        rows = [
            ('Human_Male',   'B', 'p_hm_body_a',  'p_hmbodya', 'p_hm_body_a', 'S_Male02',   '0'),
            ('Human_Female', 'B', 'p_hf_body_a',  'p_hfbodya', 'p_hf_body_a', 'S_Female02', '1'),
            ('Twilek',       'B', 'p_twil_body_a', 'p_twilbodya', 'p_twil_body_a', 'S_Male02', '2'),
            ('Bantha',       'F', '****',           '****',      'c_bantha',    'NULL',       '****'),
            ('Droid',        'B', 'n_droid_body_a', 'n_drdbdya', 'n_droid_body_a', 'NULL',   '****'),
        ]
    header = "2DA V2.0\n\n"
    col_names = "   label       modeltype  modela          texa        race          supermodel  normalhead\n"
    data_lines = ""
    for i, r in enumerate(rows):
        data_lines += f"{i}  {'  '.join(r)}\n"
    return (header + col_names + data_lines).encode('ascii')


def _make_heads_2da() -> bytes:
    """Minimal heads.2da: 3 head rows."""
    header = "2DA V2.0\n\n"
    col_names = "   label           head              headtexe   headtexve  headtexvve headtexvvve\n"
    rows = [
        "0   Human_Male_Head  p_hm_head_a01     ****       ****       ****       ****\n",
        "1   Human_Female_Head p_hf_head_a01    ****       ****       ****       ****\n",
        "2   Twilek_Head       p_twil_head_a01  ****       ****       ****       ****\n",
    ]
    return (header + col_names + "".join(rows)).encode('ascii')


class _FakeTwoDA:
    """Minimal TwoDA-like object backed by a list of dicts."""
    def __init__(self, rows):
        self._rows = rows

    def __len__(self): return len(self._rows)

    def __getitem__(self, idx):
        if idx < 0 or idx >= len(self._rows):
            raise IndexError(idx)
        return _FakeRow(self._rows[idx])


class _FakeRow:
    def __init__(self, d): self._d = d
    def get(self, col, default=''): return self._d.get(col, default)


def _make_appearance_tda():
    """Build a _FakeTwoDA simulating a minimal appearance.2da."""
    rows = [
        {'modeltype': 'B', 'modela': 'p_hm_body_a', 'texa': 'p_hmbodya',
         'race': 'p_hm_body_a', 'supermodel': 'S_Male02', 'normalhead': '0',
         'modelscale': '1.0'},
        {'modeltype': 'B', 'modela': 'p_hf_body_a', 'texa': 'p_hfbodya',
         'race': 'p_hf_body_a', 'supermodel': 'S_Female02', 'normalhead': '1',
         'modelscale': '1.0'},
        {'modeltype': 'B', 'modela': 'p_twil_body_a', 'texa': 'p_twilbodya',
         'race': 'p_twil_body_a', 'supermodel': 'S_Male02', 'normalhead': '2',
         'modelscale': '1.0'},
        {'modeltype': 'F', 'modela': '****', 'texa': '****',
         'race': 'c_bantha', 'supermodel': 'NULL', 'normalhead': '****',
         'modelscale': '1.0'},
    ]
    return _FakeTwoDA(rows)


def _make_heads_tda():
    rows = [
        {'head': 'p_hm_head_a01', 'headtexe': '****', 'headtexve': '****',
         'headtexvve': '****', 'headtexvvve': '****'},
        {'head': 'p_hf_head_a01', 'headtexe': '****', 'headtexve': '****',
         'headtexvve': '****', 'headtexvvve': '****'},
        {'head': 'p_twil_head_a01', 'headtexe': '****', 'headtexve': '****',
         'headtexvve': '****', 'headtexvvve': '****'},
    ]
    return _FakeTwoDA(rows)


# ─────────────────────────────────────────────────────────────────────────────
#  Minimal KotorModel-like stub that all_nodes() works for
# ─────────────────────────────────────────────────────────────────────────────

class _FakeAnim:
    """Minimal animation stub."""
    def __init__(self, name, length=1.0):
        self.name = name
        self.length = length
        self.node_anims = {}
        self.events = []


class _FakeNode:
    """Minimal node stub (avoids inner-class closure issues)."""
    def __init__(self, node_name, is_bone_flag=False, has_verts=False):
        self.name      = node_name
        self.is_bone   = is_bone_flag
        self.vertices  = [(0.0, 0.0, 0.0)] if has_verts else []
        self.verts     = self.vertices
        self.children  = []
        self.parent    = None


class _FakeModel:
    """Minimal KotorModel-like stub."""
    def __init__(self, model_name, anims=None):
        self.name       = model_name
        self.animations = list(anims or [])
        self.supermodel = 'NULL'
        self.root_node  = _FakeNode(model_name)

    def all_nodes(self):
        """DFS traversal."""
        stack = [self.root_node]
        while stack:
            n = stack.pop()
            yield n
            for c in reversed(getattr(n, 'children', [])):
                stack.append(c)


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 3.3: UTC → CreatureAppearance pipeline
# ─────────────────────────────────────────────────────────────────────────────

class TestUTCAppearancePipeline:
    """Tests for resolve_utc_appearance() with a real GFF parser."""

    def _resolve(self, appearance_id, good_evil=50, armor_bodyvar=None):
        from src.core.creature_appearance import resolve_utc_appearance
        utc = _make_utc_gff(appearance_id, good_evil)
        app2da = _make_appearance_tda()
        heads2da = _make_heads_tda()
        return resolve_utc_appearance(utc, app2da, heads2da,
                                       armor_bodyvar=armor_bodyvar)

    def test_appearance_id_zero_resolves_human_male_body(self):
        ap = self._resolve(0)
        assert ap.appearance_id == 0
        assert ap.body_model is not None
        assert 'hm_body' in (ap.body_model or '').lower()

    def test_modeltype_B_uses_modela_column(self):
        ap = self._resolve(0)
        assert ap.modeltype == 'B'

    def test_body_tex_has_variation_suffix(self):
        ap = self._resolve(0)
        assert ap.body_tex is not None
        assert ap.body_tex.endswith('01'), f"Expected '01' suffix, got {ap.body_tex!r}"

    def test_head_model_resolved_from_normalhead(self):
        ap = self._resolve(0)
        assert ap.head_model is not None
        assert 'head' in (ap.head_model or '').lower()

    def test_supermodel_resolved(self):
        ap = self._resolve(0)
        assert ap.supermodel.lower() == 's_male02'

    def test_non_B_modeltype_uses_race_column(self):
        ap = self._resolve(3)   # Bantha row: modeltype='F', race='c_bantha'
        assert ap.modeltype == 'F'
        assert ap.race_model is not None
        assert 'bantha' in (ap.race_model or '').lower()
        assert ap.body_model is None  # no bodyslot for non-B types

    def test_primary_model_non_B_returns_race(self):
        ap = self._resolve(3)
        assert 'bantha' in (ap.primary_model or '').lower()

    def test_out_of_range_appearance_id_returns_empty(self):
        from src.core.creature_appearance import resolve_utc_appearance
        utc = _make_utc_gff(9999, 50)
        ap2 = _make_appearance_tda()
        ap = resolve_utc_appearance(utc, ap2, None)
        assert ap.body_model is None
        assert ap.head_model is None

    def test_evil_alignment_no_evil_col_uses_texa(self):
        # alignment=5 → evil, but there is no 'texaevil' in our fake 2DA → falls back to texa
        ap = self._resolve(0, good_evil=5)
        assert ap.body_tex is not None

    def test_armor_bodyvar_selects_model_col(self):
        from src.core.creature_appearance import resolve_utc_appearance
        # Add row with modelb column
        rows = [{'modeltype': 'B', 'modela': 'body_a', 'modelb': 'body_b',
                  'texa': 'texa', 'texb': 'texb',
                  'race': 'body_a', 'supermodel': 'S_Male02', 'normalhead': '****',
                  'modelscale': '1.0'}]
        app2 = _FakeTwoDA(rows)
        utc  = _make_utc_gff(0, 50)
        ap   = resolve_utc_appearance(utc, app2, None, armor_bodyvar='b')
        assert ap.body_model == 'body_b'
        assert ap.body_tex is not None and 'texb' in ap.body_tex.lower()

    def test_repr_includes_key_fields(self):
        ap = self._resolve(0)
        r = repr(ap)
        assert 'id=0' in r
        assert 'modeltype=' in r


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 3.4: Animation controller improvements
# ─────────────────────────────────────────────────────────────────────────────

class TestControllerTypeMapping:
    """Verify CTRL_TYPE_NAMES in mdl_parser is correct and deduplicated."""

    def _get_ctrl_names(self):
        """Extract CTRL_TYPE_NAMES by parsing the _parse_controllers source."""
        import textwrap
        import src.core.mdl_parser as m
        import inspect
        src_text = inspect.getsource(m.MDLBinaryParser._parse_controllers)
        # Extract the CTRL_TYPE_NAMES block
        start = src_text.index('CTRL_TYPE_NAMES = {')
        # Find the matching closing brace
        depth = 0
        end = start
        for i, ch in enumerate(src_text[start:]):
            if ch == '{': depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = start + i + 1
                    break
        code = src_text[start:end]
        # Dedent so exec() doesn't get an IndentationError
        code = textwrap.dedent(code)
        ns = {}
        exec(compile(code, '<ctrl_names>', 'exec'), ns)
        return ns.get('CTRL_TYPE_NAMES', {})

    def test_detonate_502_in_ctrl_names(self):
        """Detonate controller (KotOR.js id=502) must be present."""
        names = self._get_ctrl_names()
        assert 502 in names, "Detonate (502) missing from CTRL_TYPE_NAMES"
        assert names[502] == 'detonate'

    def test_no_duplicate_keys(self):
        """CTRL_TYPE_NAMES must not have duplicate keys (shadowed entries)."""
        import re, inspect
        import src.core.mdl_parser as m
        src_text = inspect.getsource(m.MDLBinaryParser._parse_controllers)
        # Find all integer keys inside the CTRL_TYPE_NAMES block
        start = src_text.index('CTRL_TYPE_NAMES = {')
        # Find the closing brace of just this dict
        depth = 0
        pos = start
        for i, ch in enumerate(src_text[start:]):
            if ch == '{': depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = start + i + 1
                    break
        block = src_text[start:end]
        keys = [int(m2.group(1)) for m2 in re.finditer(r'^\s+(\d+)\s*:', block, re.MULTILINE)]
        assert len(keys) == len(set(keys)), \
            f"Duplicate keys in CTRL_TYPE_NAMES: {sorted(k for k in keys if keys.count(k)>1)}"

    def test_light_radius_is_88(self):
        """KotOR.js OdysseyModelControllerType.Radius = 88 (not 80)."""
        names = self._get_ctrl_names()
        # 88 should map to 'radius' (shared between Light.Radius and Emitter.BirthRate)
        assert 88 in names, "Type 88 missing from CTRL_TYPE_NAMES"
        # Must NOT map to 'vertical_displacement' (old incorrect name for 88)
        assert names[88] not in ('vertical_displacement',), \
            f"Type 88 maps to wrong name: {names[88]!r}"

    def test_alpha_132_present(self):
        """CTRL_MESH_ALPHA = 132 must be present."""
        names = self._get_ctrl_names()
        assert 132 in names
        assert names[132] == 'alpha'

    def test_selfillum_100_present(self):
        """CTRL_MESH_SELFILLUMCOLOR = 100 must be present."""
        names = self._get_ctrl_names()
        assert 100 in names
        assert names[100] == 'selfillum_color'

    def test_all_kotor_js_emitter_types_present(self):
        """All KotOR.js OdysseyModelControllerType emitter IDs must be in the map."""
        # Taken verbatim from KotOR.js OdysseyModelControllerType.ts
        kotor_js_emitter = {
            80, 84, 88, 92, 96, 100, 104, 108, 112, 116, 120, 124, 128, 132,
            136, 140, 144, 148, 152, 156, 160, 164, 168, 172, 176, 180, 184,
            188, 192, 196, 200, 216, 220, 224, 228, 232, 236, 240, 252, 256,
            260, 264, 268, 272, 284, 380, 392, 502,
        }
        names = self._get_ctrl_names()
        missing = kotor_js_emitter - set(names.keys())
        assert not missing, f"Missing emitter controller IDs: {sorted(missing)}"

    def test_canonical_cols_502_present(self):
        """Canonical column count for Detonate (502) must be 1."""
        import re, inspect
        import src.core.mdl_parser as m
        src_text = inspect.getsource(m.MDLBinaryParser._parse_controllers)
        start = src_text.index('_CANONICAL_COLS = {')
        # Find closing brace
        depth = 0
        pos_s = start
        for i, ch in enumerate(src_text[start:]):
            if ch == '{': depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = start + i + 1
                    break
        block = src_text[start:end]
        ns = {}
        exec(compile(block, '<canon>', 'exec'), ns)
        canon = ns['_CANONICAL_COLS']
        assert 502 in canon, "Detonate (502) missing from _CANONICAL_COLS"
        assert canon[502] == 1, f"Expected 1 column for Detonate, got {canon[502]}"

    def test_position_orientation_scale_present(self):
        """Base node controllers (8, 20, 36) must always be present."""
        names = self._get_ctrl_names()
        assert names.get(8)  == 'position'
        assert names.get(20) == 'orientation'
        assert names.get(36) == 'scale'


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 3.7: Supermodel animation inheritance
# ─────────────────────────────────────────────────────────────────────────────

class TestMergeSupermodelAnimations:
    """Phase 3.7: Animation inheritance from supermodel."""

    def test_parent_anims_copied_to_childless_child(self):
        """Child with no animations gets all parent animations."""
        from src.core.creature_appearance import merge_supermodel_animations
        parent = _FakeModel('S_Male02', [_FakeAnim('idle'), _FakeAnim('walk')])
        child  = _FakeModel('p_hm_body_a', [])
        merge_supermodel_animations(child, parent)
        names = [a.name for a in child.animations]
        assert 'idle' in names
        assert 'walk' in names

    def test_child_existing_anims_not_overwritten(self):
        """Child animations with same name as parent must NOT be replaced."""
        from src.core.creature_appearance import merge_supermodel_animations
        child_idle = _FakeAnim('idle', length=2.0)
        parent = _FakeModel('S_Male02', [_FakeAnim('idle', length=1.0),
                                          _FakeAnim('run',  length=0.8)])
        child  = _FakeModel('p_hm_body_a', [child_idle])
        merge_supermodel_animations(child, parent)
        # child's 'idle' must keep its original length (2.0)
        child_idle_after = next(a for a in child.animations if a.name == 'idle')
        assert child_idle_after.length == 2.0, "Child 'idle' was wrongly replaced"
        # 'run' should have been added
        assert any(a.name == 'run' for a in child.animations)

    def test_case_insensitive_name_comparison(self):
        """Animation names are compared case-insensitively (KotOR is case-insensitive)."""
        from src.core.creature_appearance import merge_supermodel_animations
        parent = _FakeModel('S_Male02', [_FakeAnim('IDLE'), _FakeAnim('WALK')])
        child  = _FakeModel('body', [_FakeAnim('idle')])  # child has lowercase 'idle'
        merge_supermodel_animations(child, parent)
        names_lower = [a.name.lower() for a in child.animations]
        # IDLE should NOT be duplicated
        assert names_lower.count('idle') == 1, "idle duplicated in child"
        # WALK should be added
        assert 'walk' in names_lower

    def test_none_parent_handled_gracefully(self):
        """merge_supermodel_animations(child, None) must not raise."""
        from src.core.creature_appearance import merge_supermodel_animations
        child = _FakeModel('body', [_FakeAnim('idle')])
        result = merge_supermodel_animations(child, None)
        assert result is child  # same object returned

    def test_none_child_handled_gracefully(self):
        """merge_supermodel_animations(None, parent) must return None safely."""
        from src.core.creature_appearance import merge_supermodel_animations
        parent = _FakeModel('S_Male02', [_FakeAnim('idle')])
        result = merge_supermodel_animations(None, parent)
        assert result is None

    def test_parent_with_no_animations_is_noop(self):
        """If parent has no animations, child is unchanged."""
        from src.core.creature_appearance import merge_supermodel_animations
        child  = _FakeModel('body', [_FakeAnim('idle')])
        parent = _FakeModel('S_Male02', [])
        merge_supermodel_animations(child, parent)
        assert len(child.animations) == 1

    def test_animations_are_shallow_copies(self):
        """Animations copied to child must be new objects (shallow copies), not same refs."""
        from src.core.creature_appearance import merge_supermodel_animations
        parent_anim = _FakeAnim('run')
        parent = _FakeModel('S_Male02', [parent_anim])
        child  = _FakeModel('body', [])
        merge_supermodel_animations(child, parent)
        child_run = next(a for a in child.animations if a.name == 'run')
        # Must be a different object to prevent aliasing
        assert child_run is not parent_anim, "Animation was aliased, not copied"

    def test_total_animation_count(self):
        """Parent adds N new anims; child ends up with child+N anims."""
        from src.core.creature_appearance import merge_supermodel_animations
        parent_anims = [_FakeAnim(n) for n in ['idle', 'walk', 'run', 'attack', 'die']]
        parent = _FakeModel('S_Male02', parent_anims)
        child  = _FakeModel('body', [_FakeAnim('custom_anim')])
        merge_supermodel_animations(child, parent)
        assert len(child.animations) == 6  # 1 child + 5 parent


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 3.3: build_creature_model pipeline (using mock library)
# ─────────────────────────────────────────────────────────────────────────────

class _MockKeyEntry:
    def __init__(self, data): self._data = data
    def read(self): return self._data


class _MockKeyReader:
    """Minimal reader that returns resources from an in-memory dict."""
    def __init__(self, resources):
        # resources: {(resref_lower, res_type): bytes}
        self._resources = resources

    def get(self, resref, res_type):
        key = (resref.lower(), res_type)
        if key in self._resources:
            return _MockKeyEntry(self._resources[key])
        return None


class _MockLibrary:
    """Minimal GameLibrary-like stub for testing."""
    def __init__(self, k1_resources=None):
        self._k1_key = _MockKeyReader(k1_resources or {})
        self._k2_key = _MockKeyReader({})


class TestBuildCreatureModel:
    """Phase 3.3: build_creature_model() end-to-end with a mock library."""

    def test_resolve_utc_appearance_from_bytes(self):
        """resolve_utc_appearance works with a real GFF binary."""
        from src.core.creature_appearance import resolve_utc_appearance
        from src.core.twoda import TwoDA
        utc = _make_utc_gff(0, 50)
        app = TwoDA.from_bytes(_make_appearance_2da(), name='appearance')
        hds = TwoDA.from_bytes(_make_heads_2da(), name='heads')
        ap = resolve_utc_appearance(utc, app, hds)
        assert ap.appearance_id == 0
        assert ap.modeltype == 'B'
        assert ap.body_model is not None
        assert ap.supermodel.lower() == 's_male02'

    def test_parse_appearance_tables(self):
        """parse_appearance_tables returns valid TwoDA objects."""
        from src.core.creature_appearance import parse_appearance_tables
        app, hds = parse_appearance_tables(_make_appearance_2da(), _make_heads_2da())
        assert app is not None
        assert hds is not None
        assert len(app) > 0
        assert len(hds) > 0

    def test_parse_appearance_tables_no_heads(self):
        """parse_appearance_tables with heads_bytes=None returns heads=None."""
        from src.core.creature_appearance import parse_appearance_tables
        app, hds = parse_appearance_tables(_make_appearance_2da(), None)
        assert app is not None
        assert hds is None

    def test_creature_appearance_primary_model_property(self):
        """CreatureAppearance.primary_model returns body_model for B-type."""
        from src.core.creature_appearance import CreatureAppearance
        ap = CreatureAppearance(
            body_model='p_hm_body_a', modeltype='B',
            race_model='p_hm_body_a', appearance_id=0,
        )
        assert ap.primary_model == 'p_hm_body_a'

    def test_creature_appearance_primary_model_non_B(self):
        """CreatureAppearance.primary_model returns race_model for non-B types."""
        from src.core.creature_appearance import CreatureAppearance
        ap = CreatureAppearance(
            body_model=None, modeltype='F',
            race_model='c_bantha', appearance_id=3,
        )
        assert ap.primary_model == 'c_bantha'

    def test_creature_model_set_primary(self):
        """CreatureModelSet.primary returns body_model."""
        from src.core.creature_appearance import CreatureModelSet
        cms = CreatureModelSet(body_model='fake_body_object')
        assert cms.primary == 'fake_body_object'

    def test_load_utc_into_viewport_returns_none_for_missing_utc(self):
        """load_utc_into_viewport returns None when UTC is not in library."""
        from src.core.creature_appearance import load_utc_into_viewport
        lib = _MockLibrary(k1_resources={})
        result = load_utc_into_viewport('nonexistent_creature', lib, game='K1')
        assert result is None

    def test_merge_supermodel_no_parent_bones_is_noop(self):
        """merge_supermodel with parent having no bone/dummy nodes returns child unchanged."""
        from src.core.creature_appearance import merge_supermodel
        child  = _FakeModel('child',  [])
        parent = _FakeModel('parent', [])
        result = merge_supermodel(child, parent)
        assert result is child  # same object, no crash

    def test_merge_supermodel_injects_parent_bones(self):
        """merge_supermodel injects parent bone nodes into child root."""
        from src.core.creature_appearance import merge_supermodel

        # Build parent with a bone node
        parent = _FakeModel('S_Male02', [])
        bone = _FakeNode('thigh_l', is_bone_flag=True)
        parent.root_node.children.append(bone)

        # Child has only a mesh
        child  = _FakeModel('body', [])

        merge_supermodel(child, parent)
        child_names = [n.name for n in child.all_nodes()]
        assert 'thigh_l' in child_names, \
            f"Expected 'thigh_l' injected into child; got {child_names}"

    def test_merge_supermodel_no_duplicate_bones(self):
        """merge_supermodel must NOT inject a bone already in the child."""
        from src.core.creature_appearance import merge_supermodel

        existing_bone = _FakeNode('thigh_l', is_bone_flag=True)
        parent = _FakeModel('S_Male02', [])
        parent_bone = _FakeNode('thigh_l', is_bone_flag=True)
        parent.root_node.children.append(parent_bone)

        child = _FakeModel('body', [])
        child.root_node.children.append(existing_bone)

        merge_supermodel(child, parent)

        # Count thigh_l occurrences
        count = sum(1 for n in child.all_nodes() if n.name.lower() == 'thigh_l')
        assert count == 1, f"Expected 1 thigh_l, found {count}"

    def test_merge_supermodel_recursive_subtree_injection(self):
        """
        merge_supermodel must recursively inject child bones of parent bones,
        preserving the hierarchy (not flattening everything to child root).

        Bug fixed: previously, copy.copy(pnode) + children=[] was used, which
        injected only the direct children of parent_root but NOT their children.
        A KotOR skeleton has: root → pelvis → spine → chest → … etc.
        All levels must be injected, not just the first level.
        """
        from src.core.creature_appearance import merge_supermodel

        # Build a 3-level parent skeleton:
        #   parent_root → pelvis → spine
        parent = _FakeModel('S_Male02', [])
        pelvis = _FakeNode('pelvis', is_bone_flag=True)
        spine  = _FakeNode('spine',  is_bone_flag=True)
        # Wire spine as a child of pelvis (not of parent_root)
        pelvis.children.append(spine)
        spine.parent = pelvis
        parent.root_node.children.append(pelvis)
        pelvis.parent = parent.root_node

        # Child only has a mesh, no bones yet
        child = _FakeModel('body', [])

        merge_supermodel(child, parent)
        child_names = {n.name.lower() for n in child.all_nodes()}

        assert 'pelvis' in child_names, \
            f"Expected 'pelvis' injected into child; got {child_names}"
        assert 'spine' in child_names, \
            f"Expected 'spine' injected into child (recursive); got {child_names}"

    def test_merge_supermodel_idempotent_on_double_call(self):
        """
        Calling merge_supermodel twice must not inject duplicate bones.
        The idempotency check uses child_names built from all_nodes() at the
        start of the second call, so previously-injected bones are found and
        skipped.
        """
        from src.core.creature_appearance import merge_supermodel

        parent = _FakeModel('S_Male02', [])
        bone = _FakeNode('hip', is_bone_flag=True)
        parent.root_node.children.append(bone)
        bone.parent = parent.root_node

        child = _FakeModel('body', [])

        merge_supermodel(child, parent)  # first call
        merge_supermodel(child, parent)  # second call

        count = sum(1 for n in child.all_nodes() if n.name.lower() == 'hip')
        assert count == 1, f"Double merge produced {count} copies of 'hip'"

    def test_gff_parser_reads_good_evil_field(self):
        """_GFFParser correctly reads GoodEvil BYTE field."""
        from src.core.creature_appearance import _GFFParser
        utc = _make_utc_gff(appearance_id=5, good_evil=30)
        p = _GFFParser(utc)
        assert p.fields.get('GoodEvil') == 30

    def test_gff_parser_reads_appearance_type_field(self):
        """_GFFParser correctly reads Appearance_Type WORD field."""
        from src.core.creature_appearance import _GFFParser
        utc = _make_utc_gff(appearance_id=42, good_evil=50)
        p = _GFFParser(utc)
        assert p.fields.get('Appearance_Type') == 42


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 3.4: Controller round-trip through ASCII MDL parser
# ─────────────────────────────────────────────────────────────────────────────

class TestControllerRoundTrip:
    """Verify node properties survive the ASCII MDL → model_data round trip."""

    def test_selfillumcolor_parsed_from_ascii(self):
        """selfillumcolor in ASCII MDL is stored as 'selfillum' on the node."""
        from src.core.mdl_parser import MDLAsciiParser
        ascii_mdl = """\
newmodel testself
  setanimationscale 1.0
  setsupermodel testself NULL

beginmodelgeom testself
  node trimesh mesh1
    parent NULL
    selfillumcolor 0.5 0.5 0.5
    render 1
    vertices 4
      0.0  0.0  0.0
      1.0  0.0  0.0
      1.0  1.0  0.0
      0.0  1.0  0.0
    faces 2
      0 1 2   1 0 0 0
      0 2 3   1 0 0 0
    tverts 4
      0.0 0.0
      1.0 0.0
      1.0 1.0
      0.0 1.0
  endnode
endmodelgeom

donemodel testself
"""
        model = MDLAsciiParser().parse_string(ascii_mdl)
        nodes = list(model.all_nodes())
        mesh  = next((n for n in nodes if n.name == 'mesh1'), None)
        assert mesh is not None
        assert hasattr(mesh, 'selfillum')
        assert abs(mesh.selfillum[0] - 0.5) < 1e-5

    def test_alpha_parsed_from_ascii(self):
        """alpha command in ASCII MDL node is stored as node.alpha."""
        from src.core.mdl_parser import MDLAsciiParser
        ascii_mdl = """\
newmodel testalpha
  setanimationscale 1.0
  setsupermodel testalpha NULL

beginmodelgeom testalpha
  node trimesh amesh
    parent NULL
    alpha 0.75
    render 1
    vertices 3
      0.0 0.0 0.0
      1.0 0.0 0.0
      0.5 1.0 0.0
    faces 1
      0 1 2   1 0 0 0
    tverts 3
      0.0 0.0
      1.0 0.0
      0.5 1.0
  endnode
endmodelgeom

donemodel testalpha
"""
        model = MDLAsciiParser().parse_string(ascii_mdl)
        nodes = list(model.all_nodes())
        mesh  = next((n for n in nodes if n.name == 'amesh'), None)
        assert mesh is not None
        assert abs(mesh.alpha - 0.75) < 1e-5


# ─────────────────────────────────────────────────────────────────────────────
#  Integration: GFF binary → 2DA → model name chain
# ─────────────────────────────────────────────────────────────────────────────

class TestGFFTo2DAChain:
    """
    Ensure the complete chain from GFF bytes → appearance_id → 2DA row →
    model resref works end-to-end without a game installation.
    """

    def test_full_chain_human_male(self):
        """appearance_id=0 → Human_Male → modela=p_hm_body_a."""
        from src.core.creature_appearance import resolve_utc_appearance
        from src.core.twoda import TwoDA
        utc = _make_utc_gff(appearance_id=0)
        app = TwoDA.from_bytes(_make_appearance_2da(), name='appearance')
        hds = TwoDA.from_bytes(_make_heads_2da(), name='heads')
        ap = resolve_utc_appearance(utc, app, hds)
        assert ap.body_model == 'p_hm_body_a', f"Got {ap.body_model!r}"
        # body_tex is lowercased: texa='p_hmbodya' + '01' = 'p_hmbodya01'
        assert ap.body_tex == 'p_hmbodya01', f"Got {ap.body_tex!r}"
        assert ap.head_model == 'p_hm_head_a01', f"Got {ap.head_model!r}"
        assert ap.supermodel.lower() == 's_male02'

    def test_full_chain_human_female(self):
        """appearance_id=1 → Human_Female → modela=p_hf_body_a."""
        from src.core.creature_appearance import resolve_utc_appearance
        from src.core.twoda import TwoDA
        utc = _make_utc_gff(appearance_id=1)
        app = TwoDA.from_bytes(_make_appearance_2da(), name='appearance')
        hds = TwoDA.from_bytes(_make_heads_2da(), name='heads')
        ap = resolve_utc_appearance(utc, app, hds)
        assert ap.body_model == 'p_hf_body_a'
        assert ap.supermodel.lower() == 's_female02'

    def test_full_chain_bantha_race_only(self):
        """appearance_id=3 → Bantha → F type → race=c_bantha, no head."""
        from src.core.creature_appearance import resolve_utc_appearance
        from src.core.twoda import TwoDA
        utc = _make_utc_gff(appearance_id=3)
        app = TwoDA.from_bytes(_make_appearance_2da(), name='appearance')
        ap = resolve_utc_appearance(utc, app, None)
        assert ap.modeltype == 'F'
        assert ap.race_model == 'c_bantha'
        assert ap.body_model is None
        assert ap.head_model is None
        assert ap.primary_model == 'c_bantha'

    def test_full_chain_supermodel_null_for_bantha(self):
        """Bantha has supermodel=NULL — correctly parsed as 'NULL' string."""
        from src.core.creature_appearance import resolve_utc_appearance
        from src.core.twoda import TwoDA
        utc = _make_utc_gff(appearance_id=3)
        app = TwoDA.from_bytes(_make_appearance_2da(), name='appearance')
        ap = resolve_utc_appearance(utc, app, None)
        assert ap.supermodel.upper() == 'NULL'

    def test_body_tex_is_lowercase(self):
        """body_tex must always be returned lowercase (for file-system lookup)."""
        from src.core.creature_appearance import resolve_utc_appearance
        from src.core.twoda import TwoDA
        utc = _make_utc_gff(appearance_id=0)
        app = TwoDA.from_bytes(_make_appearance_2da(), name='appearance')
        ap = resolve_utc_appearance(utc, app, None)
        if ap.body_tex:
            assert ap.body_tex == ap.body_tex.lower(), \
                f"body_tex not lowercase: {ap.body_tex!r}"

    def test_head_model_is_lowercase(self):
        """head_model must always be returned lowercase."""
        from src.core.creature_appearance import resolve_utc_appearance
        from src.core.twoda import TwoDA
        utc = _make_utc_gff(appearance_id=0)
        app = TwoDA.from_bytes(_make_appearance_2da(), name='appearance')
        hds = TwoDA.from_bytes(_make_heads_2da(), name='heads')
        ap = resolve_utc_appearance(utc, app, hds)
        if ap.head_model:
            assert ap.head_model == ap.head_model.lower(), \
                f"head_model not lowercase: {ap.head_model!r}"
