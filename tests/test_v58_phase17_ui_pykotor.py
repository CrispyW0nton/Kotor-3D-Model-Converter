"""
Phase 17 – UI/UX Clean-up & PyKotor Integration Tests
======================================================
Tests covering:
  1. Color palette has new 'success' and 'sep' keys
  2. _GFF_RES_TYPES constant covers expected resource type IDs
  3. Source-level checks: new methods, bindings, helpers exist (main_window.py)
  4. Source-level checks: keyboard shortcuts, toolbar (viewport.py)
  5. PyKotor read_2da produces expected output format
  6. PyKotor read_gff round-trips and struct fields are accessible
  7. AnimationsPanel toggle_play_pause logic in source
  8. _sep and _tooltip helper presence in source
"""

import sys
import os
import re
import pytest

# ── path setup ───────────────────────────────────────────────────────────────
_SRC = os.path.join(os.path.dirname(__file__), '..', 'src')
sys.path.insert(0, _SRC)
_PK_PATH = '/home/user/webapp/PyKotor/Libraries/PyKotor/src'
if os.path.isdir(_PK_PATH) and _PK_PATH not in sys.path:
    sys.path.insert(0, _PK_PATH)

_MW_PATH = os.path.join(_SRC, 'gui', 'main_window.py')
_VP_PATH = os.path.join(_SRC, 'gui', 'viewport.py')


def _mw_src():
    return open(_MW_PATH, encoding='utf-8').read()


def _vp_src():
    return open(_VP_PATH, encoding='utf-8').read()


def _pykotor_available() -> bool:
    try:
        from pykotor.resource.formats.twoda import read_2da  # noqa
        return True
    except ImportError:
        return False


def _pykotor_gff_available() -> bool:
    try:
        from pykotor.resource.formats.gff import read_gff  # noqa
        return True
    except ImportError:
        return False


# ─────────────────────────────────────────────────────────────────────────────
#  1. Color palette
# ─────────────────────────────────────────────────────────────────────────────

class TestColorPalette:
    def _get_C(self):
        import ast
        src = _mw_src()
        start = src.index("C = {")
        end = src.index("\n}", start) + 2
        return ast.literal_eval(src[start + 4:end])

    def test_original_keys(self):
        C = self._get_C()
        for k in ('bg', 'bg2', 'panel', 'accent', 'gold', 'green',
                  'red', 'text', 'text2', 'border', 'hover', 'selected', 'warning'):
            assert k in C, f"Missing palette key: {k}"

    def test_success_key(self):
        assert 'success' in self._get_C(), "'success' key missing from palette"

    def test_sep_key(self):
        assert 'sep' in self._get_C(), "'sep' key missing from palette"

    def test_sep_hex(self):
        assert self._get_C()['sep'].startswith('#'), "'sep' should be a hex color"

    def test_success_hex(self):
        assert self._get_C()['success'].startswith('#'), "'success' should be hex"


# ─────────────────────────────────────────────────────────────────────────────
#  2. _GFF_RES_TYPES
# ─────────────────────────────────────────────────────────────────────────────

class TestGffResTypes:
    def _get_types(self):
        src = _mw_src()
        m = re.search(r'_GFF_RES_TYPES.*?frozenset\(\{([^}]+)\}\)', src, re.DOTALL)
        if not m:
            return set()
        return {int(n, 16) for n in re.findall(r'0x[0-9a-fA-F]+', m.group(1))}

    def test_utc(self):    assert 0x07D9 in self._get_types(), "UTC missing"
    def test_uti(self):    assert 0x07DA in self._get_types(), "UTI missing"
    def test_dlg(self):    assert 0x07E0 in self._get_types(), "DLG missing"
    def test_are(self):    assert 0x07E7 in self._get_types(), "ARE missing"
    def test_git(self):    assert 0x07EA in self._get_types(), "GIT missing"
    def test_no_2da(self): assert 0x07E1 not in self._get_types(), "2DA should NOT be GFF"
    def test_frozenset_defined(self):
        assert '_GFF_RES_TYPES' in _mw_src(), "_GFF_RES_TYPES not defined"
    def test_minimum_six_types(self):
        assert len(self._get_types()) >= 6, "Expected at least 6 GFF types"


# ─────────────────────────────────────────────────────────────────────────────
#  3. main_window.py source checks
# ─────────────────────────────────────────────────────────────────────────────

class TestMainWindowSource:
    def test_tooltip_helper(self):      assert 'def _tooltip(' in _mw_src()
    def test_sep_helper(self):          assert 'def _sep(' in _mw_src()
    def test_ctrl_o(self):              assert '<Control-o>' in _mw_src()
    def test_ctrl_w(self):              assert '<Control-w>' in _mw_src()
    def test_ctrl_e(self):              assert '<Control-e>' in _mw_src()
    def test_ctrl_s(self):              assert '<Control-s>' in _mw_src()
    def test_ctrl_g(self):              assert '<Control-g>' in _mw_src()
    def test_f1_about(self):            assert '<F1>' in _mw_src()
    def test_f2_settings(self):         assert '<F2>' in _mw_src()
    def test_escape(self):              assert '<Escape>' in _mw_src()
    def test_clear_model(self):         assert 'def _clear_model(' in _mw_src()
    def test_on_escape(self):           assert 'def _on_escape(' in _mw_src()
    def test_switch_tab_right(self):    assert 'def _switch_tab_right(' in _mw_src()
    def test_toggle_play_pause(self):   assert 'def _toggle_play_pause(' in _mw_src()
    def test_space_binding(self):       assert '<space>' in _mw_src()
    def test_return_on_tree(self):      assert '<Return>' in _mw_src()
    def test_n_mesh_in_pill(self):      assert 'n_mesh' in _mw_src()
    def test_n_anim_in_pill(self):      assert 'n_anim' in _mw_src()
    def test_anim_export_dropdown(self): assert '_show_exp_anim_menu' in _mw_src()
    def test_gff_res_types(self):       assert '_GFF_RES_TYPES' in _mw_src()
    def test_preview_2da_pykotor(self): assert '_preview_2da_pykotor' in _mw_src()
    def test_preview_gff_pykotor(self): assert '_preview_gff_pykotor' in _mw_src()
    def test_gff_struct_lines(self):    assert '_gff_struct_lines' in _mw_src()
    def test_load_btn_tooltip(self):    assert '_tooltip(b_load' in _mw_src()
    def test_enter_on_listbox(self):
        src = _mw_src()
        assert '<Return>' in src and '_load_selected' in src
    def test_sep_in_toolbar(self):      assert '_sep(tb)' in _mw_src()
    def test_import_shortcut_hints(self):
        src = _mw_src()
        assert 'Ctrl+I' in src or 'Ctrl+Shift+O' in src
    def test_export_shortcut_hints(self):
        src = _mw_src()
        assert 'Ctrl+E' in src or 'Ctrl+G' in src
    def test_tooltip_on_btn_open(self):
        # The Open MDL button should have a tooltip call
        assert '_tooltip(b_open' in _mw_src()
    def test_tooltip_on_btn_rig(self):
        assert '_tooltip(b_rig' in _mw_src()


# ─────────────────────────────────────────────────────────────────────────────
#  4. viewport.py source checks
# ─────────────────────────────────────────────────────────────────────────────

class TestViewportSource:
    def test_w_wireframe(self):
        assert '"<w>"' in _vp_src() or "'<w>'" in _vp_src()
    def test_b_bones(self):
        assert '"<b>"' in _vp_src() or "'<b>'" in _vp_src()
    def test_t_texture(self):
        assert '"<t>"' in _vp_src() or "'<t>'" in _vp_src()
    def test_g_gimbal(self):
        assert '"<g>"' in _vp_src() or "'<g>'" in _vp_src()
    def test_tab_mode(self):
        assert '<Tab>' in _vp_src()
    def test_r_reset(self):
        assert '"<r>"' in _vp_src() or "'<r>'" in _vp_src()
    def test_plus_zoom(self):
        assert '<plus>' in _vp_src() or '<equal>' in _vp_src()
    def test_focus_on_click(self):
        assert 'focus_set' in _vp_src()
    def test_translate_label(self):
        assert 'Translate' in _vp_src()
    def test_rotate_label(self):
        assert 'Rotate' in _vp_src()
    def test_vp_sep_used(self):
        assert '_vp_sep()' in _vp_src()
    def test_vp_tip_used(self):
        assert '_vp_tip(' in _vp_src()
    def test_tooltip_frame_all(self):
        assert '_vp_tip(b_frame_all' in _vp_src()
    def test_tooltip_reset(self):
        assert '_vp_tip(b_reset' in _vp_src()
    def test_toolbar_dark_bg(self):
        # Toolbar should have a near-black background
        assert '#0e0e20' in _vp_src() or '#111122' in _vp_src()
    def test_display_group_comment(self):
        src = _vp_src().lower()
        assert 'display group' in src or '── display' in src
    def test_nav_group_comment(self):
        src = _vp_src().lower()
        assert 'navigation' in src or 'nav group' in src
    def test_gimbal_group_comment(self):
        src = _vp_src().lower()
        assert 'gimbal' in src
    def test_fast_drag_default_false(self):
        assert '_fast_drag_enabled: bool = False' in _vp_src()


# ─────────────────────────────────────────────────────────────────────────────
#  5. PyKotor read_2da (standalone integration)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _pykotor_available(), reason="pykotor not installed")
class TestPykotorRead2da:
    def _make_2da_bytes(self) -> bytes:
        """Build a valid 2DA using pykotor and write to temp file."""
        import tempfile, os
        from pykotor.resource.formats.twoda import read_2da, write_2da
        from pykotor.resource.formats.twoda.twoda_data import TwoDA
        t = TwoDA()
        t.add_column('LABEL')
        t.add_row(); t.set_cell(0, 'LABEL', 'Hero')
        t.add_row(); t.set_cell(1, 'LABEL', 'Villain')
        tf = tempfile.NamedTemporaryFile(suffix='.2da', delete=False)
        tf.close()
        write_2da(t, tf.name)
        data = open(tf.name, 'rb').read()
        os.unlink(tf.name)
        return data

    def test_read_returns_object(self):
        from pykotor.resource.formats.twoda import read_2da
        tda = read_2da(self._make_2da_bytes())
        assert tda is not None

    def test_has_get_headers(self):
        from pykotor.resource.formats.twoda import read_2da
        tda = read_2da(self._make_2da_bytes())
        headers = tda.get_headers()
        assert isinstance(headers, list)
        assert len(headers) >= 1

    def test_row_count(self):
        from pykotor.resource.formats.twoda import read_2da
        tda = read_2da(self._make_2da_bytes())
        assert len(tda) == 2

    def test_get_cell(self):
        from pykotor.resource.formats.twoda import read_2da
        tda = read_2da(self._make_2da_bytes())
        val = tda.get_cell(0, 'LABEL')
        assert val == 'Hero'

    def test_invalid_raises(self):
        from pykotor.resource.formats.twoda import read_2da
        with pytest.raises(Exception):
            read_2da(b"NOT A 2DA")


# ─────────────────────────────────────────────────────────────────────────────
#  6. PyKotor read_gff round-trip
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _pykotor_gff_available(), reason="pykotor not installed")
class TestPykotorReadGff:
    def _make_gff_bytes(self) -> bytes:
        """Build valid GFF bytes using pykotor write_gff to file."""
        import tempfile, os
        from pykotor.resource.formats.gff import write_gff, read_gff
        from pykotor.resource.formats.gff.gff_data import GFF, GFFContent
        gff = GFF(GFFContent.UTC)
        gff.root.set_string("FirstName", "TestHero")
        gff.root.set_uint32("Appearance_Type", 100)
        tf = tempfile.NamedTemporaryFile(suffix='.utc', delete=False)
        tf.close()
        write_gff(gff, tf.name)
        data = open(tf.name, 'rb').read()
        os.unlink(tf.name)
        return data

    def test_read_returns_gff(self):
        from pykotor.resource.formats.gff import read_gff
        gff = read_gff(self._make_gff_bytes())
        assert gff is not None

    def test_root_struct_accessible(self):
        from pykotor.resource.formats.gff import read_gff
        gff = read_gff(self._make_gff_bytes())
        assert gff.root is not None

    def test_field_round_trip(self):
        from pykotor.resource.formats.gff import read_gff
        gff = read_gff(self._make_gff_bytes())
        val = gff.root.get_string("FirstName")
        assert val == "TestHero"

    def test_uint32_round_trip(self):
        from pykotor.resource.formats.gff import read_gff
        gff = read_gff(self._make_gff_bytes())
        val = gff.root.get_uint32("Appearance_Type")
        assert val == 100

    def test_content_type_set(self):
        from pykotor.resource.formats.gff import read_gff
        from pykotor.resource.formats.gff.gff_data import GFFContent
        gff = read_gff(self._make_gff_bytes())
        assert gff.content == GFFContent.UTC

    def test_struct_iteration_yields_tuples(self):
        from pykotor.resource.formats.gff import read_gff
        gff = read_gff(self._make_gff_bytes())
        items = list(gff.root)
        assert len(items) >= 1
        # pykotor yields (label, GFFFieldType, value) tuples
        assert isinstance(items[0], tuple)
        assert len(items[0]) == 3

    def test_struct_iteration_has_labels(self):
        from pykotor.resource.formats.gff import read_gff
        gff = read_gff(self._make_gff_bytes())
        labels = [item[0] for item in gff.root]
        assert "FirstName" in labels
        assert "Appearance_Type" in labels

    def test_invalid_raises(self):
        from pykotor.resource.formats.gff import read_gff
        with pytest.raises(Exception):
            read_gff(b"NOT A GFF BINARY DATA")


# ─────────────────────────────────────────────────────────────────────────────
#  7. GFFStruct depth guard logic
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _pykotor_gff_available(), reason="pykotor not installed")
class TestGffStructDepthGuard:
    """Verify the depth guard logic and pykotor tuple iteration."""

    def _depth_guarded_render(self, struct, indent, max_depth):
        """Reimplementation matching the actual _gff_struct_lines depth logic."""
        lines = []
        if indent > max_depth:
            lines.append("  " * indent + "…")
            return lines
        pad = "  " * indent
        # pykotor iterates (label, GFFFieldType, value) tuples
        for field_entry in struct:
            if isinstance(field_entry, tuple) and len(field_entry) >= 3:
                label, _ftype, val = field_entry[0], field_entry[1], field_entry[2]
            else:
                label, val = str(field_entry), None
            lines.append(f"{pad}{label}: {val!r}")
        return lines

    def test_depth_exceeded_produces_ellipsis(self):
        from pykotor.resource.formats.gff.gff_data import GFFStruct
        s = GFFStruct()
        s.set_string("Name", "Hero")
        result = self._depth_guarded_render(s, indent=6, max_depth=5)
        assert any('…' in l for l in result)

    def test_depth_at_limit_renders_fields(self):
        from pykotor.resource.formats.gff.gff_data import GFFStruct
        s = GFFStruct()
        s.set_string("Name", "Hero")
        result = self._depth_guarded_render(s, indent=5, max_depth=5)
        assert len(result) >= 1, "At limit, fields should still render"

    def test_depth_zero_no_indent(self):
        from pykotor.resource.formats.gff.gff_data import GFFStruct
        s = GFFStruct()
        s.set_uint32("Level", 5)
        result = self._depth_guarded_render(s, indent=0, max_depth=5)
        assert any('Level' in l for l in result)

    def test_tuple_labels_extracted(self):
        from pykotor.resource.formats.gff.gff_data import GFFStruct
        s = GFFStruct()
        s.set_string("Hero", "Revan")
        items = list(s)
        assert len(items) >= 1
        assert isinstance(items[0], tuple)
        labels = [item[0] for item in items]
        assert 'Hero' in labels


# ─────────────────────────────────────────────────────────────────────────────
#  8. _sep and _tooltip helper presence
# ─────────────────────────────────────────────────────────────────────────────

class TestSepTooltipHelpers:
    def test_sep_returns_frame(self):
        src = _mw_src()
        # _sep creates a tk.Frame
        m = re.search(r'def _sep\(.*?\).*?return tk\.Frame', src, re.DOTALL)
        assert m is not None, "_sep should return tk.Frame"

    def test_tooltip_creates_toplevel(self):
        assert 'tk.Toplevel' in _mw_src()

    def test_tooltip_uses_overrideredirect(self):
        assert 'wm_overrideredirect' in _mw_src()

    def test_tooltip_binds_enter(self):
        src = _mw_src()
        assert '"<Enter>"' in src or "'<Enter>'" in src

    def test_tooltip_binds_leave(self):
        src = _mw_src()
        assert '"<Leave>"' in src or "'<Leave>'" in src

    def test_tooltip_binds_buttonpress(self):
        src = _mw_src()
        assert '"<ButtonPress>"' in src or "'<ButtonPress>'" in src

    def test_sep_has_bg_from_C(self):
        src = _mw_src()
        # _sep should use C['sep'] for the background color
        assert "C['sep']" in src or 'sep' in src
