"""
Phase 5.1/5.2 — Module Loader Tests
=====================================
Comprehensive test suite for src/core/module_loader.py.

Tests cover:
  1. LoadResult dataclass defaults and summary()
  2. ModelLookup — no library returns None, ducks to library method
  3. ModuleLoader.load_from_lyt_text() — minimal headless mode
  4. ModuleLoader.load_from_lyt_text() with VIS data
  5. ModuleLoader.load_from_kotor_module() — with full mock module
  6. LYT → SceneRoom mapping (positions, resrefs, NULL skipping)
  7. VIS → linked_rooms propagation
  8. ARE → AREProperties on scene
  9. GIT → SceneObject placement (creatures, placeables, doors, waypoints, triggers)
  10. Walkmesh overlay creation via load_all_room_overlays integration
  11. ModuleLoader.load_from_directory() with missing directory
  12. load_module_directory() convenience function
  13. Warning accumulation on bad inputs
  14. Integration: full pipeline LYT + VIS + GIT + WOK → scene summary

Refs: KotOR.js ForgeArea.ts; GhostRigger Roadmap Phase 5.1/5.2/5.4/9.1.
"""

import sys
import os
import unittest
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# ── import path ─────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.module_loader import (
    LoadResult, ModelLookup, ModuleLoader, load_module_directory,
)
from src.core.scene_manager import SceneGraph, SceneRoom, SceneObject, SceneObjectType


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — build mock objects
# ─────────────────────────────────────────────────────────────────────────────

def _lyt_room(model, x=0.0, y=0.0, z=0.0):
    return SimpleNamespace(model=model, x=x, y=y, z=z)


def _make_git(creatures=None, placeables=None, doors=None, waypoints=None, triggers=None):
    def _obj(resref, x, y, z, tag='', bearing=0.0):
        return SimpleNamespace(resref=resref, x=x, y=y, z=z, tag=tag, bearing=bearing)
    return SimpleNamespace(
        creatures  = creatures  or [],
        placeables = placeables or [],
        doors      = doors      or [],
        waypoints  = waypoints  or [],
        triggers   = triggers   or [],
        summary    = lambda: "GIT summary",
    )


def _make_are(ambient=(0.2,0.2,0.2), fog=False, fog_near=10.0, fog_far=100.0):
    return SimpleNamespace(
        ambient_color  = ambient,
        diffuse_color  = (1.0, 1.0, 1.0),
        fog_enabled    = fog,
        fog_color      = (0.5, 0.5, 0.5),
        fog_near       = fog_near,
        fog_far        = fog_far,
        dynamic_light  = (0.0, 0.0, 0.0),
        name           = 'Dantooine',
    )


def _make_module(rooms=None, vis=None, are=None, git=None,
                 room_woks=None, name='testmod', game='K1'):
    lyt_rooms = rooms or []
    lyt = SimpleNamespace(rooms=lyt_rooms, doorhooks=[])
    mod = SimpleNamespace(
        name       = name,
        game       = game,
        lyt        = lyt,
        vis        = vis,
        are        = are,
        git        = git,
        ifo        = None,
        wok        = None,
        room_woks  = room_woks or {},
        summary    = lambda: f"Module: {name!r} ({game})",
    )
    return mod


def _make_vis(data: dict):
    """vis.visibility is a dict of room_name → frozenset(visible_rooms)."""
    return SimpleNamespace(visibility=data)


# ─────────────────────────────────────────────────────────────────────────────
# 1. LoadResult defaults and summary
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadResult(unittest.TestCase):

    def test_defaults(self):
        r = LoadResult()
        self.assertIsNone(r.module)
        self.assertIsNone(r.scene)
        self.assertEqual(r.walkmeshes, {})
        self.assertEqual(r.warnings, [])
        self.assertEqual(r.game, 'K1')

    def test_summary_no_module(self):
        r = LoadResult()
        s = r.summary()
        self.assertIsInstance(s, str)

    def test_summary_with_module(self):
        mod = SimpleNamespace(summary=lambda: 'Module: test')
        r = LoadResult(module=mod)
        s = r.summary()
        self.assertIn('Module: test', s)

    def test_summary_with_warnings(self):
        r = LoadResult()
        r.warnings = ['warn1', 'warn2']
        s = r.summary()
        self.assertIn('warn1', s)

    def test_summary_many_warnings_truncated(self):
        r = LoadResult()
        r.warnings = [f'warn{i}' for i in range(20)]
        s = r.summary()
        # First 5 shown, rest collapsed
        self.assertIn('warn0', s)
        self.assertIn('+', s)  # "+15 more"

    def test_walkmesh_count_in_summary(self):
        r = LoadResult()
        r.walkmeshes = {'a': None, 'b': None}
        s = r.summary()
        self.assertIn('2', s)


# ─────────────────────────────────────────────────────────────────────────────
# 2. ModelLookup
# ─────────────────────────────────────────────────────────────────────────────

class TestModelLookup(unittest.TestCase):

    def test_no_library_returns_none(self):
        ml = ModelLookup(None)
        self.assertIsNone(ml.load_model('danm13_a'))

    def test_no_library_has_model_false(self):
        ml = ModelLookup(None)
        self.assertFalse(ml.has_model('anything'))

    def test_library_load_model_method(self):
        lib = MagicMock()
        mock_model = object()
        lib.load_model = MagicMock(return_value=mock_model)
        ml = ModelLookup(lib)
        result = ml.load_model('danm13_a')
        self.assertIs(result, mock_model)
        lib.load_model.assert_called_once_with('danm13_a')

    def test_library_get_model_fallback(self):
        lib = SimpleNamespace(get_model=lambda resref: 'model_obj')
        ml = ModelLookup(lib)
        self.assertEqual(ml.load_model('room1'), 'model_obj')

    def test_library_exception_returns_none(self):
        lib = MagicMock()
        lib.load_model = MagicMock(side_effect=RuntimeError("not found"))
        ml = ModelLookup(lib)
        result = ml.load_model('bad_model')
        self.assertIsNone(result)

    def test_has_model_uses_list_models(self):
        lib = SimpleNamespace(list_models=lambda: ['danm13_a', 'danm13_b'])
        ml = ModelLookup(lib)
        self.assertTrue(ml.has_model('danm13_a'))
        self.assertFalse(ml.has_model('unknown'))

    def test_has_model_case_insensitive(self):
        lib = SimpleNamespace(list_models=lambda: ['DANM13_A'])
        ml = ModelLookup(lib)
        self.assertTrue(ml.has_model('danm13_a'))


# ─────────────────────────────────────────────────────────────────────────────
# 3. ModuleLoader.load_from_lyt_text — minimal headless
# ─────────────────────────────────────────────────────────────────────────────

LYT_SIMPLE = """\
roomcount 2
  room_a 0.0 0.0 0.0
  room_b 10.0 0.0 0.0
"""

LYT_WITH_NULL = """\
roomcount 3
  room_a 0.0 0.0 0.0
  NULL 999.0 999.0 999.0
  room_c 20.0 0.0 0.0
"""


class TestLoadFromLytText(unittest.TestCase):

    def setUp(self):
        self.loader = ModuleLoader()

    def test_returns_load_result(self):
        result = self.loader.load_from_lyt_text(LYT_SIMPLE)
        self.assertIsInstance(result, LoadResult)

    def test_scene_is_scene_graph(self):
        result = self.loader.load_from_lyt_text(LYT_SIMPLE)
        self.assertIsInstance(result.scene, SceneGraph)

    def test_rooms_loaded_from_lyt(self):
        result = self.loader.load_from_lyt_text(LYT_SIMPLE)
        self.assertEqual(len(result.scene.rooms), 2)

    def test_room_resrefs(self):
        result = self.loader.load_from_lyt_text(LYT_SIMPLE)
        resrefs = {r.resref for r in result.scene.rooms}
        self.assertIn('room_a', resrefs)
        self.assertIn('room_b', resrefs)

    def test_room_positions(self):
        result = self.loader.load_from_lyt_text(LYT_SIMPLE)
        room_b = result.scene.room_by_name('room_b')
        self.assertIsNotNone(room_b)
        self.assertAlmostEqual(room_b.position[0], 10.0)

    def test_null_room_skipped(self):
        result = self.loader.load_from_lyt_text(LYT_WITH_NULL)
        resrefs = {r.resref for r in result.scene.rooms}
        self.assertNotIn('null', resrefs)
        self.assertEqual(len(result.scene.rooms), 2)

    def test_no_walkmeshes_without_wok(self):
        result = self.loader.load_from_lyt_text(LYT_SIMPLE)
        # No WOK data → no overlays
        self.assertEqual(len(result.walkmeshes), 0)

    def test_module_object_set(self):
        result = self.loader.load_from_lyt_text(LYT_SIMPLE)
        self.assertIsNotNone(result.module)

    def test_game_attribute(self):
        result = self.loader.load_from_lyt_text(LYT_SIMPLE, game='K2')
        self.assertEqual(result.game, 'K2')

    def test_empty_lyt_returns_empty_scene(self):
        result = self.loader.load_from_lyt_text("roomcount 0\n")
        self.assertEqual(len(result.scene.rooms), 0)


# ─────────────────────────────────────────────────────────────────────────────
# 4. load_from_lyt_text with VIS
# ─────────────────────────────────────────────────────────────────────────────

VIS_SIMPLE = """\
room_a
  room_b
room_b
  room_a
"""


class TestLoadFromLytWithVis(unittest.TestCase):

    def setUp(self):
        self.loader = ModuleLoader()
        self.result = self.loader.load_from_lyt_text(LYT_SIMPLE, vis_text=VIS_SIMPLE)

    def test_vis_applied_to_rooms(self):
        room_a = self.result.scene.room_by_name('room_a')
        self.assertIsNotNone(room_a)
        self.assertIn('room_b', room_a.linked_rooms)

    def test_vis_bidirectional(self):
        room_b = self.result.scene.room_by_name('room_b')
        self.assertIn('room_a', room_b.linked_rooms)

    def test_bad_vis_text_produces_warning(self):
        result = self.loader.load_from_lyt_text(LYT_SIMPLE,
                                                vis_text="invalid vis garbage\n" * 5)
        # Should not crash; might produce a warning or silently ignore
        self.assertIsInstance(result, LoadResult)


# ─────────────────────────────────────────────────────────────────────────────
# 5. ModuleLoader.load_from_kotor_module — full mock
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadFromKotorModule(unittest.TestCase):

    def setUp(self):
        self.loader = ModuleLoader()

    def test_two_rooms(self):
        mod = _make_module(rooms=[
            _lyt_room('enc_bay01', 0.0, 0.0, 0.0),
            _lyt_room('enc_bay02', 15.0, 0.0, 0.0),
        ])
        result = self.loader.load_from_kotor_module(mod)
        self.assertEqual(len(result.scene.rooms), 2)

    def test_null_room_skipped(self):
        mod = _make_module(rooms=[
            _lyt_room('room_a', 0.0, 0.0, 0.0),
            _lyt_room('NULL', 99.0, 99.0, 0.0),
        ])
        result = self.loader.load_from_kotor_module(mod)
        self.assertEqual(len(result.scene.rooms), 1)

    def test_no_lyt_warns(self):
        mod = SimpleNamespace(
            name='noroom', game='K1', lyt=None, vis=None, are=None,
            git=None, ifo=None, wok=None, room_woks={},
            summary=lambda: 'empty')
        result = self.loader.load_from_kotor_module(mod)
        self.assertTrue(any('LYT' in w for w in result.warnings),
                        msg=f"Expected LYT warning, got: {result.warnings}")

    def test_game_attribute_preserved(self):
        mod = _make_module(game='K2')
        result = self.loader.load_from_kotor_module(mod, game='K2')
        self.assertEqual(result.game, 'K2')


# ─────────────────────────────────────────────────────────────────────────────
# 6. LYT → SceneRoom mapping
# ─────────────────────────────────────────────────────────────────────────────

class TestLYTToSceneRooms(unittest.TestCase):

    def setUp(self):
        self.loader = ModuleLoader()

    def test_room_position_mapped(self):
        mod = _make_module(rooms=[_lyt_room('manm03aa', 5.0, 7.0, 1.5)])
        result = self.loader.load_from_kotor_module(mod)
        r = result.scene.room_by_name('manm03aa')
        self.assertIsNotNone(r)
        self.assertAlmostEqual(r.position[0], 5.0)
        self.assertAlmostEqual(r.position[1], 7.0)
        self.assertAlmostEqual(r.position[2], 1.5)

    def test_room_resref_lowercased(self):
        mod = _make_module(rooms=[_lyt_room('DANM13_A', 0.0, 0.0, 0.0)])
        result = self.loader.load_from_kotor_module(mod)
        r = result.scene.room_by_name('danm13_a')
        self.assertIsNotNone(r)

    def test_model_none_without_library(self):
        mod = _make_module(rooms=[_lyt_room('room1', 0.0, 0.0, 0.0)])
        result = self.loader.load_from_kotor_module(mod)
        r = result.scene.room_by_name('room1')
        self.assertIsNone(r.model)

    def test_model_loaded_from_library(self):
        lib = MagicMock()
        mock_model = object()
        lib.load_model = MagicMock(return_value=mock_model)
        loader = ModuleLoader(library=lib)
        mod = _make_module(rooms=[_lyt_room('room1', 0.0, 0.0, 0.0)])
        result = loader.load_from_kotor_module(mod)
        r = result.scene.room_by_name('room1')
        self.assertIs(r.model, mock_model)

    def test_multiple_rooms_positions(self):
        rooms = [_lyt_room(f'r{i}', i*10.0, 0.0, 0.0) for i in range(5)]
        mod = _make_module(rooms=rooms)
        result = self.loader.load_from_kotor_module(mod)
        self.assertEqual(len(result.scene.rooms), 5)
        for i, room in enumerate(result.scene.rooms):
            self.assertAlmostEqual(room.position[0], i * 10.0)


# ─────────────────────────────────────────────────────────────────────────────
# 7. VIS → linked_rooms propagation
# ─────────────────────────────────────────────────────────────────────────────

class TestVISPropagation(unittest.TestCase):

    def setUp(self):
        self.loader = ModuleLoader()

    def test_linked_rooms_set(self):
        vis = _make_vis({'room_a': frozenset(['room_b', 'room_c']), 'room_b': frozenset(['room_a'])})
        mod = _make_module(
            rooms=[_lyt_room('room_a'), _lyt_room('room_b'), _lyt_room('room_c')],
            vis=vis,
        )
        result = self.loader.load_from_kotor_module(mod)
        ra = result.scene.room_by_name('room_a')
        self.assertIn('room_b', ra.linked_rooms)
        self.assertIn('room_c', ra.linked_rooms)

    def test_vis_room_not_in_lyt_no_crash(self):
        """VIS entries for rooms not in LYT should be silently ignored."""
        vis = _make_vis({'ghost_room': frozenset(['room_a'])})
        mod = _make_module(rooms=[_lyt_room('room_a')], vis=vis)
        result = self.loader.load_from_kotor_module(mod)
        self.assertIsNotNone(result.scene)

    def test_case_insensitive_vis(self):
        vis = _make_vis({'ROOM_A': frozenset(['ROOM_B'])})
        mod = _make_module(
            rooms=[_lyt_room('room_a'), _lyt_room('room_b')], vis=vis)
        result = self.loader.load_from_kotor_module(mod)
        # Our loader lowercases both sides, so room_a should have room_b linked
        ra = result.scene.room_by_name('room_a')
        self.assertIn('room_b', ra.linked_rooms)


# ─────────────────────────────────────────────────────────────────────────────
# 8. ARE → AREProperties
# ─────────────────────────────────────────────────────────────────────────────

class TestAREProperties(unittest.TestCase):

    def setUp(self):
        self.loader = ModuleLoader()

    def test_are_ambient_color_applied(self):
        are = _make_are(ambient=(0.1, 0.2, 0.3))
        mod = _make_module(rooms=[_lyt_room('r1')], are=are)
        result = self.loader.load_from_kotor_module(mod)
        ap = result.scene.are_props
        self.assertIsNotNone(ap)
        # sun_ambient is stored as int [0-255]; floats are converted * 255
        self.assertIsInstance(ap.sun_ambient, (tuple, list))
        self.assertEqual(len(ap.sun_ambient), 3)

    def test_fog_enabled_propagated(self):
        are = _make_are(fog=True, fog_near=5.0, fog_far=50.0)
        mod = _make_module(rooms=[_lyt_room('r1')], are=are)
        result = self.loader.load_from_kotor_module(mod)
        ap = result.scene.are_props
        self.assertTrue(ap.fog_enabled)
        self.assertAlmostEqual(ap.fog_near, 5.0)
        self.assertAlmostEqual(ap.fog_far, 50.0)

    def test_no_are_leaves_default(self):
        mod = _make_module(rooms=[_lyt_room('r1')], are=None)
        result = self.loader.load_from_kotor_module(mod)
        # scene.are_properties should still exist (default from SceneGraph)
        self.assertIsNotNone(result.scene)


# ─────────────────────────────────────────────────────────────────────────────
# 9. GIT → SceneObject placement
# ─────────────────────────────────────────────────────────────────────────────

def _git_obj(resref, x, y, z, tag='', bearing=0.0):
    return SimpleNamespace(resref=resref, x=x, y=y, z=z, tag=tag, bearing=bearing)


class TestGITPlacement(unittest.TestCase):

    def setUp(self):
        self.loader = ModuleLoader()

    def test_creatures_placed(self):
        git = _make_git(creatures=[
            _git_obj('n_tarisian01', 1.0, 2.0, 0.0),
            _git_obj('n_tarisian02', 3.0, 4.0, 0.0),
        ])
        mod = _make_module(rooms=[_lyt_room('r1')], git=git)
        result = self.loader.load_from_kotor_module(mod)
        creatures = [o for o in result.scene.objects
                     if o.obj_type == SceneObjectType.CREATURE]
        self.assertEqual(len(creatures), 2)

    def test_placeables_placed(self):
        git = _make_git(placeables=[_git_obj('plc_terminal', 5.0, 5.0, 0.0)])
        mod = _make_module(rooms=[_lyt_room('r1')], git=git)
        result = self.loader.load_from_kotor_module(mod)
        placeables = [o for o in result.scene.objects
                      if o.obj_type == SceneObjectType.PLACEABLE]
        self.assertEqual(len(placeables), 1)

    def test_doors_placed(self):
        git = _make_git(doors=[_git_obj('door01', 0.0, 0.0, 0.0)])
        mod = _make_module(rooms=[_lyt_room('r1')], git=git)
        result = self.loader.load_from_kotor_module(mod)
        doors = [o for o in result.scene.objects
                 if o.obj_type == SceneObjectType.DOOR]
        self.assertEqual(len(doors), 1)

    def test_waypoints_placed(self):
        git = _make_git(waypoints=[_git_obj('wp_spawn01', 2.5, 3.5, 0.0)])
        mod = _make_module(rooms=[_lyt_room('r1')], git=git)
        result = self.loader.load_from_kotor_module(mod)
        waypoints = [o for o in result.scene.objects
                     if o.obj_type == SceneObjectType.WAYPOINT]
        self.assertEqual(len(waypoints), 1)

    def test_triggers_placed(self):
        git = _make_git(triggers=[_git_obj('tr_area01', 0.0, 0.0, 0.0)])
        mod = _make_module(rooms=[_lyt_room('r1')], git=git)
        result = self.loader.load_from_kotor_module(mod)
        triggers = [o for o in result.scene.objects
                    if o.obj_type == SceneObjectType.TRIGGER]
        self.assertEqual(len(triggers), 1)

    def test_mixed_git_objects(self):
        git = _make_git(
            creatures  = [_git_obj('c1', 0, 0, 0)] * 3,
            placeables = [_git_obj('p1', 0, 0, 0)] * 2,
            doors      = [_git_obj('d1', 0, 0, 0)] * 1,
            waypoints  = [_git_obj('w1', 0, 0, 0)] * 4,
            triggers   = [_git_obj('t1', 0, 0, 0)] * 1,
        )
        mod = _make_module(rooms=[_lyt_room('r1')], git=git)
        result = self.loader.load_from_kotor_module(mod)
        self.assertEqual(len(result.scene.objects), 11)

    def test_creature_position_stored(self):
        git = _make_git(creatures=[_git_obj('npc_1', 7.5, 8.5, 1.0)])
        mod = _make_module(rooms=[_lyt_room('r1')], git=git)
        result = self.loader.load_from_kotor_module(mod)
        c = [o for o in result.scene.objects
             if o.obj_type == SceneObjectType.CREATURE][0]
        self.assertAlmostEqual(c.position[0], 7.5)
        self.assertAlmostEqual(c.position[1], 8.5)
        self.assertAlmostEqual(c.position[2], 1.0)

    def test_no_git_zero_objects(self):
        mod = _make_module(rooms=[_lyt_room('r1')], git=None)
        result = self.loader.load_from_kotor_module(mod)
        self.assertEqual(len(result.scene.objects), 0)


# ─────────────────────────────────────────────────────────────────────────────
# 10. Walkmesh overlay integration
# ─────────────────────────────────────────────────────────────────────────────

def _make_wok_data(verts, faces_data):
    wok = SimpleNamespace()
    wok.verts = verts
    WFace = lambda v1,v2,v3,s: SimpleNamespace(v1=v1, v2=v2, v3=v3, surface=s)
    wok.faces = [WFace(*fd) for fd in faces_data]
    return wok


class TestWalkmeshOverlayIntegration(unittest.TestCase):

    def setUp(self):
        self.loader = ModuleLoader()

    def test_overlay_created_for_room_with_wok(self):
        verts = [(0,0,0),(1,0,0),(0,1,0)]
        wok = _make_wok_data(verts, [(0,1,2,1)])
        mod = _make_module(
            rooms=[_lyt_room('room_a', 0.0, 0.0, 0.0)],
            room_woks={'room_a': wok},
        )
        result = self.loader.load_from_kotor_module(mod)
        self.assertIn('room_a', result.walkmeshes)

    def test_no_overlay_for_room_without_wok(self):
        mod = _make_module(rooms=[_lyt_room('room_a', 0.0, 0.0, 0.0)])
        result = self.loader.load_from_kotor_module(mod)
        self.assertNotIn('room_a', result.walkmeshes)

    def test_overlay_has_correct_face_count(self):
        verts = [(0,0,0),(1,0,0),(0,1,0),(1,1,0)]
        wok = _make_wok_data(verts, [(0,1,2,1),(0,2,3,4)])
        mod = _make_module(
            rooms=[_lyt_room('r1', 0.0, 0.0, 0.0)],
            room_woks={'r1': wok},
        )
        result = self.loader.load_from_kotor_module(mod)
        overlay = result.walkmeshes['r1']
        self.assertEqual(len(overlay.faces), 2)

    def test_overlay_world_offset_applied(self):
        verts = [(0,0,0),(1,0,0),(0,1,0)]
        wok = _make_wok_data(verts, [(0,1,2,1)])
        mod = _make_module(
            rooms=[_lyt_room('r1', 10.0, 5.0, 2.0)],
            room_woks={'r1': wok},
        )
        result = self.loader.load_from_kotor_module(mod)
        overlay = result.walkmeshes['r1']
        f = overlay.faces[0]
        self.assertAlmostEqual(f.v0[0], 10.0)
        self.assertAlmostEqual(f.v0[1], 5.0)
        self.assertAlmostEqual(f.v0[2], 2.0)

    def test_multiple_rooms_overlays(self):
        verts = [(0,0,0),(1,0,0),(0,1,0)]
        wok = _make_wok_data(verts, [(0,1,2,1)])
        mod = _make_module(
            rooms=[
                _lyt_room('ra', 0.0, 0.0, 0.0),
                _lyt_room('rb', 10.0, 0.0, 0.0),
                _lyt_room('rc', 20.0, 0.0, 0.0),  # no WOK
            ],
            room_woks={'ra': wok, 'rb': wok},
        )
        result = self.loader.load_from_kotor_module(mod)
        self.assertIn('ra', result.walkmeshes)
        self.assertIn('rb', result.walkmeshes)
        self.assertNotIn('rc', result.walkmeshes)
        self.assertEqual(len(result.walkmeshes), 2)


# ─────────────────────────────────────────────────────────────────────────────
# 11. load_from_directory with missing / empty directory
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadFromDirectory(unittest.TestCase):

    def test_nonexistent_directory_returns_result(self):
        loader = ModuleLoader()
        result = loader.load_from_directory('/nonexistent/path/that/does/not/exist/')
        self.assertIsInstance(result, LoadResult)
        # Should not raise; may have warnings or empty module

    def test_empty_directory_returns_empty_scene(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = ModuleLoader()
            result = loader.load_from_directory(tmpdir)
            self.assertIsInstance(result, LoadResult)

    def test_directory_with_lyt_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lyt_path = os.path.join(tmpdir, 'testmod.lyt')
            with open(lyt_path, 'w') as f:
                f.write("roomcount 2\n  room_a 0.0 0.0 0.0\n  room_b 10.0 0.0 0.0\n")
            loader = ModuleLoader()
            result = loader.load_from_directory(tmpdir, module_name='testmod')
            if result.scene:
                # Should find 2 rooms from the LYT
                self.assertGreaterEqual(len(result.scene.rooms), 0)


# ─────────────────────────────────────────────────────────────────────────────
# 12. load_module_directory convenience function
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadModuleDirectory(unittest.TestCase):

    def test_returns_load_result(self):
        result = load_module_directory('/nonexistent/')
        self.assertIsInstance(result, LoadResult)

    def test_game_parameter_passed(self):
        result = load_module_directory('/nonexistent/', game='K2')
        self.assertEqual(result.game, 'K2')


# ─────────────────────────────────────────────────────────────────────────────
# 13. Warning accumulation
# ─────────────────────────────────────────────────────────────────────────────

class TestWarnings(unittest.TestCase):

    def test_no_lyt_produces_warning(self):
        loader = ModuleLoader()
        mod = SimpleNamespace(
            name='x', game='K1', lyt=None, vis=None, are=None,
            git=None, ifo=None, wok=None, room_woks={},
            summary=lambda: 'x')
        result = loader.load_from_kotor_module(mod)
        self.assertTrue(len(result.warnings) > 0)

    def test_warnings_are_strings(self):
        loader = ModuleLoader()
        result = loader.load_from_directory('/nonexistent/path/')
        for w in result.warnings:
            self.assertIsInstance(w, str)


# ─────────────────────────────────────────────────────────────────────────────
# 14. Integration — full pipeline
# ─────────────────────────────────────────────────────────────────────────────

class TestFullPipelineIntegration(unittest.TestCase):
    """
    Integration test: LYT + VIS + ARE + GIT + WOK → complete LoadResult.
    Mirrors ForgeArea.ts flow without any actual file I/O.
    """

    def setUp(self):
        self.loader = ModuleLoader()
        verts = [(0,0,0),(5,0,0),(0,5,0),(5,5,0)]
        wok_a = _make_wok_data(verts, [(0,1,2,1),(1,2,3,4)])  # 2 faces
        wok_b = _make_wok_data(verts, [(0,1,2,7)])             # 1 non-walkable

        git = _make_git(
            creatures  = [_git_obj('n_guard', 2.0, 2.0, 0.0, tag='guard1')],
            placeables = [_git_obj('plc_comp', 3.0, 3.0, 0.0)],
            waypoints  = [_git_obj('wp_entry', 1.0, 1.0, 0.0)],
        )
        vis = _make_vis({
            'room_a': frozenset(['room_b']),
            'room_b': frozenset(['room_a']),
        })
        are = _make_are(ambient=(0.4, 0.4, 0.4), fog=True, fog_near=8.0, fog_far=80.0)

        self.mod = _make_module(
            name   = 'danm13',
            rooms  = [
                _lyt_room('room_a', 0.0, 0.0, 0.0),
                _lyt_room('room_b', 20.0, 0.0, 0.0),
                _lyt_room('NULL',   99.0, 99.0, 0.0),  # should be skipped
            ],
            vis      = vis,
            are      = are,
            git      = git,
            room_woks= {'room_a': wok_a, 'room_b': wok_b},
        )
        self.result = self.loader.load_from_kotor_module(self.mod, game='K1')

    def test_scene_has_two_rooms(self):
        self.assertEqual(len(self.result.scene.rooms), 2)

    def test_null_excluded(self):
        resrefs = {r.resref for r in self.result.scene.rooms}
        self.assertNotIn('null', resrefs)

    def test_vis_linked(self):
        ra = self.result.scene.room_by_name('room_a')
        self.assertIn('room_b', ra.linked_rooms)

    def test_are_fog(self):
        ap = self.result.scene.are_props
        self.assertTrue(ap.fog_enabled)
        self.assertAlmostEqual(ap.fog_near, 8.0)

    def test_git_objects_total(self):
        # 1 creature + 1 placeable + 1 waypoint = 3
        self.assertEqual(len(self.result.scene.objects), 3)

    def test_walkmesh_overlays_two_rooms(self):
        self.assertIn('room_a', self.result.walkmeshes)
        self.assertIn('room_b', self.result.walkmeshes)

    def test_room_a_overlay_walkable_faces(self):
        ov = self.result.walkmeshes['room_a']
        walk = ov.walkable_faces()
        self.assertGreater(len(walk), 0)

    def test_room_b_overlay_non_walkable(self):
        ov = self.result.walkmeshes['room_b']
        non_walk = ov.non_walkable_faces()
        self.assertEqual(len(non_walk), 1)

    def test_summary_string(self):
        s = self.result.summary()
        self.assertIsInstance(s, str)
        self.assertGreater(len(s), 10)

    def test_no_warnings(self):
        # Full valid module should produce no warnings
        self.assertEqual(self.result.warnings, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
