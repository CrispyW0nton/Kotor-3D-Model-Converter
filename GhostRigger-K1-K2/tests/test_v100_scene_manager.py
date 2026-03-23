"""
Tests for Phase 5 — Scene Manager (scene_manager.py)
=====================================================
Covers:
  * Frustum class: Gribb/Hartmann plane extraction, sphere test, AABB test
  * AREProperties: from_are_data, ambient_float, fog_color_float, has_grass
  * SceneRoom / SceneObject dataclasses
  * SceneGraph: room management, VIS connectivity, frustum culling,
    current-room detection, object queries
  * SceneManager.build_scene: NULL room skipping, GIT objects, ARE props
  * SceneManager.load_room_models: bounds update

References:
  Gregory §12.5, Ericson §4.3.2, KotOR.js ForgeArea.ts/ForgeRoom.ts,
  PyKotor frustum.py (299 lines), GhostRigger Roadmap Phase 5.
"""
import math
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.scene_manager import (
    Plane, Frustum,
    AREProperties, SceneRoom, SceneObject, SceneObjectType,
    SceneGraph, SceneManager,
    _dot3, _sub3, _add3, _scale3, _norm3, _cross3,
    ModelLookup,
)

# ── Helpers ────────────────────────────────────────────────────────────────

def _make_room(name, pos=(0,0,0), bb_min=(-5,-5,0), bb_max=(5,5,3)):
    r = SceneRoom(resref=name, position=pos, bb_min=bb_min, bb_max=bb_max)
    r.bounding_r = math.sqrt((bb_max[0]-bb_min[0])**2+(bb_max[1]-bb_min[1])**2)*0.5
    return r

def _make_are_stub(**kw):
    class _A:
        pass
    a = _A()
    a.sun_ambient = kw.get('sun_ambient', (64,64,64))
    a.sun_diffuse = kw.get('sun_diffuse', (255,255,255))
    a.sun_fog     = kw.get('sun_fog', 0)
    a.fog_color   = kw.get('fog_color', (0,0,0))
    a.fog_near    = kw.get('fog_near', 100.0)
    a.fog_far     = kw.get('fog_far', 200.0)
    a._raw        = kw.get('raw', {})
    return a

def _lyt_rooms(*args):
    class _R:
        def __init__(self, nm, x, y, z):
            self.model=nm; self.x=x; self.y=y; self.z=z
    return [_R(*a) for a in args]

def _make_module(rooms=None, vis=None, are=None, git=None):
    class _M: pass
    m = _M()
    class _L: pass
    l = _L(); l.rooms = rooms or []
    m.lyt = l
    if vis is not None:
        class _V: pass
        v=_V(); v.visibility=vis; m.vis=v
    else:
        m.vis = None
    m.are = are; m.git = git
    m.name='test'; m.game='K1'; m.room_woks={}
    return m

def _make_git(creatures=None, placeables=None, doors=None, waypoints=None, triggers=None):
    class _G:
        def summary(self): return "GIT stub"
    g=_G()
    def _o(**kw):
        class _OBJ: pass
        o=_OBJ()
        for k,v in kw.items(): setattr(o,k,v)
        return o
    g.creatures  = [_o(resref=c[0],x=c[1],y=c[2],z=c[3],bearing=0)
                    for c in (creatures or [])]
    g.placeables = [_o(resref=p[0],x=p[1],y=p[2],z=p[3],bearing=0)
                    for p in (placeables or [])]
    g.doors      = [_o(resref=d[0],tag=d[1] if len(d)>1 else '',
                       x=d[2] if len(d)>2 else 0,y=d[3] if len(d)>3 else 0,
                       z=d[4] if len(d)>4 else 0,bearing=0,
                       linked_to='',linked_to_module='')
                    for d in (doors or [])]
    g.waypoints  = [_o(resref=w[0],tag=w[1] if len(w)>1 else '',
                       x=w[2] if len(w)>2 else 0,y=w[3] if len(w)>3 else 0,
                       z=0,bearing=0)
                    for w in (waypoints or [])]
    g.triggers   = [_o(resref=t[0],tag=t[1] if len(t)>1 else '',
                       x=0,y=0,z=0,geometry=[],linked_to='')
                    for t in (triggers or [])]
    return g


# ── 1. Vector helpers ──────────────────────────────────────────────────────

class TestVectorHelpers(unittest.TestCase):
    def test_dot_identity(self):
        self.assertAlmostEqual(_dot3((1,0,0),(1,0,0)), 1.0)
    def test_dot_perp(self):
        self.assertAlmostEqual(_dot3((1,0,0),(0,1,0)), 0.0)
    def test_sub(self):
        self.assertEqual(_sub3((3,5,7),(1,2,3)), (2,3,4))
    def test_add(self):
        self.assertEqual(_add3((1,2,3),(4,5,6)), (5,7,9))
    def test_scale(self):
        r=_scale3((1,2,3),2.0)
        self.assertAlmostEqual(r[0],2.0); self.assertAlmostEqual(r[2],6.0)
    def test_norm_unit_x(self):
        n=_norm3((5,0,0))
        self.assertAlmostEqual(n[0],1.0); self.assertAlmostEqual(n[1],0.0)
    def test_norm_zero_fallback(self):
        n=_norm3((0,0,0))
        self.assertAlmostEqual(n[2],1.0)
    def test_cross_xy(self):
        c=_cross3((1,0,0),(0,1,0))
        self.assertAlmostEqual(c[2],1.0)

# ── 2. Plane ──────────────────────────────────────────────────────────────

class TestPlane(unittest.TestCase):
    def test_normalize_unit(self):
        p=Plane(1,0,0,-5); n=p.normalize()
        self.assertAlmostEqual(math.sqrt(n.a**2+n.b**2+n.c**2),1.0,places=6)
    def test_distance_positive(self):
        p=Plane(1,0,0,0)
        self.assertAlmostEqual(p.distance_to_point(3,0,0),3.0)
    def test_distance_negative(self):
        p=Plane(1,0,0,0)
        self.assertAlmostEqual(p.distance_to_point(-2,0,0),-2.0)
    def test_normalize_non_unit(self):
        p=Plane(3,0,4,-10); n=p.normalize()
        self.assertAlmostEqual(math.sqrt(n.a**2+n.b**2+n.c**2),1.0,places=6)
        self.assertAlmostEqual(n.a,0.6,places=5)

# ── 3. Frustum sphere ─────────────────────────────────────────────────────

class TestFrustumSphere(unittest.TestCase):
    def _f(self, near=1.0, far=50.0):
        f=Frustum()
        f.update_from_camera(pos=(0,0,0),fwd=(0,1,0),up=(0,0,1),
                              fov_h_deg=90,fov_v_deg=90,near=near,far=far)
        return f
    def test_inside(self):     self.assertTrue(self._f().test_sphere(0,10,0,1.0))
    def test_behind(self):     self.assertFalse(self._f().test_sphere(0,-10,0,0.5))
    def test_beyond_far(self): self.assertFalse(self._f(far=20).test_sphere(0,100,0,0.5))
    def test_large_radius(self): self.assertTrue(self._f().test_sphere(0,-5,0,20.0))
    def test_trivially_disabled(self):
        f=Frustum(); self.assertTrue(f.is_trivially_disabled())
    def test_configured_not_disabled(self):
        f=self._f(); self.assertFalse(f.is_trivially_disabled())

# ── 4. Frustum AABB ──────────────────────────────────────────────────────

class TestFrustumAABB(unittest.TestCase):
    def _f(self):
        f=Frustum()
        f.update_from_camera(pos=(0,0,1),fwd=(0,1,0),up=(0,0,1),
                              fov_h_deg=90,fov_v_deg=60,near=0.5,far=100)
        return f
    def test_inside_passes(self):
        self.assertTrue(self._f().test_aabb((-2,18,0),(2,22,2)))
    def test_behind_fails(self):
        self.assertFalse(self._f().test_aabb((-2,-20,0),(2,-18,2)))
    def test_beyond_far_fails(self):
        self.assertFalse(self._f().test_aabb((-2,200,0),(2,210,2)))

# ── 5. Frustum matrix ────────────────────────────────────────────────────

class TestFrustumMatrix(unittest.TestCase):
    def _ortho(self,l,r,b,t,n,f):
        w=r-l;h=t-b;d=f-n
        return [2/w,0,0,-(r+l)/w, 0,2/h,0,-(t+b)/h,
                0,0,-2/d,-(f+n)/d, 0,0,0,1.0]
    def test_inside(self):
        m=self._ortho(-10,10,-10,10,0.1,50)
        f=Frustum(); f.update_from_matrix(m)
        self.assertTrue(f.test_sphere(0,0,-25,0.1))
    def test_outside(self):
        m=self._ortho(-10,10,-10,10,0.1,50)
        f=Frustum(); f.update_from_matrix(m)
        self.assertFalse(f.test_sphere(100,0,-25,0.1))

# ── 6. AREProperties ─────────────────────────────────────────────────────

class TestAREProperties(unittest.TestCase):
    def test_defaults(self):
        ap=AREProperties()
        self.assertEqual(ap.sun_ambient,(64,64,64))
        self.assertFalse(ap.fog_enabled)
        self.assertFalse(ap.has_grass())
    def test_from_are(self):
        a=_make_are_stub(sun_ambient=(100,150,200),sun_fog=1,fog_near=10,fog_far=80)
        ap=AREProperties.from_are_data(a)
        self.assertEqual(ap.sun_ambient,(100,150,200))
        self.assertTrue(ap.fog_enabled)
        self.assertAlmostEqual(ap.fog_near,10.0)
    def test_from_none(self):
        ap=AREProperties.from_are_data(None)
        self.assertEqual(ap.sun_ambient,(64,64,64))
    def test_ambient_float(self):
        ap=AREProperties(sun_ambient=(255,128,0))
        r,g,b=ap.ambient_float()
        self.assertAlmostEqual(r,1.0); self.assertAlmostEqual(b,0.0)
    def test_fog_float(self):
        ap=AREProperties(fog_color=(0,0,255))
        r,g,b=ap.fog_color_float()
        self.assertAlmostEqual(b,1.0)
    def test_no_grass_zero_density(self):
        self.assertFalse(AREProperties(grass_density=0.0,grass_tex_name='g').has_grass())
    def test_no_grass_no_tex(self):
        self.assertFalse(AREProperties(grass_density=1.5,grass_tex_name='').has_grass())
    def test_has_grass(self):
        self.assertTrue(AREProperties(grass_density=1.5,grass_tex_name='g').has_grass())
    def test_grass_from_raw(self):
        raw={'Grass_Density':2.5,'Grass_TexName':'lava','Grass_Prob_LL':0.1}
        a=_make_are_stub(raw=raw)
        ap=AREProperties.from_are_data(a)
        self.assertAlmostEqual(ap.grass_density,2.5)
        self.assertEqual(ap.grass_tex_name,'lava')
        self.assertAlmostEqual(ap.grass_prob_ll,0.1)

# ── 7. SceneGraph rooms ───────────────────────────────────────────────────

class TestSceneGraphRooms(unittest.TestCase):
    def test_add_find(self):
        sg=SceneGraph(); r=_make_room('entrance'); sg.add_room(r)
        self.assertEqual(sg.room_by_name('entrance'),r)
        self.assertIsNone(sg.room_by_name('x'))
    def test_case_insensitive(self):
        sg=SceneGraph(); sg.add_room(_make_room('hallway'))
        self.assertIsNotNone(sg.room_by_name('HALLWAY'))
    def test_set_all_visible(self):
        sg=SceneGraph()
        for n in ('a','b','c'): sg.add_room(_make_room(n))
        sg.set_all_rooms_visible(False)
        self.assertEqual(len(sg.rooms_all_visible()),0)
        sg.set_all_rooms_visible(True)
        self.assertEqual(len(sg.rooms_all_visible()),3)
    def test_toggle(self):
        sg=SceneGraph(); sg.add_room(_make_room('r1'))
        sg.toggle_room('r1',False)
        self.assertFalse(sg.room_by_name('r1').visible)
        sg.toggle_room('r1')
        self.assertTrue(sg.room_by_name('r1').visible)
    def test_toggle_nonexistent_noop(self):
        sg=SceneGraph(); sg.toggle_room('ghost',False)  # no exception
    def test_all_visible_filters_hidden(self):
        sg=SceneGraph(); sg.add_room(_make_room('v'))
        r2=_make_room('h'); r2.visible=False; sg.add_room(r2)
        self.assertEqual(len(sg.rooms_all_visible()),1)

# ── 8. SceneGraph VIS ────────────────────────────────────────────────────

class TestSceneGraphVIS(unittest.TestCase):
    def _three_room_scene(self):
        sg=SceneGraph()
        for n,x in (('ra',0),('rb',10),('rc',20)):
            sg.add_room(_make_room(n,pos=(x,0,0)))
        sg.set_vis_data({'ra':['rb'],'rb':['ra','rc'],'rc':['rb']})
        return sg
    def test_linked_rooms_set(self):
        sg=self._three_room_scene()
        self.assertIn('rb', sg.room_by_name('ra').linked_rooms)
    def test_from_a_excludes_c(self):
        sg=self._three_room_scene(); sg.set_current_room('ra')
        names={r.resref for r in sg.visible_rooms((0,0,0))}
        self.assertIn('ra',names); self.assertIn('rb',names)
        self.assertNotIn('rc',names)
    def test_from_b_sees_all(self):
        sg=self._three_room_scene(); sg.set_current_room('rb')
        names={r.resref for r in sg.visible_rooms((10,0,0))}
        self.assertEqual(names, {'ra','rb','rc'})
    def test_no_vis_returns_all(self):
        sg=SceneGraph()
        for n in ('a','b','c'): sg.add_room(_make_room(n))
        self.assertEqual(len(sg.visible_rooms((0,0,0))),3)
    def test_vis_respects_hidden_flag(self):
        sg=self._three_room_scene()
        sg.room_by_name('rb').visible=False
        sg.set_current_room('ra')
        names={r.resref for r in sg.visible_rooms((0,0,0))}
        self.assertNotIn('rb',names)
    def test_use_vis_false_returns_all(self):
        sg=self._three_room_scene(); sg.set_current_room('ra')
        self.assertEqual(len(sg.visible_rooms((0,0,0),use_vis=False)),3)
    def test_visible_rooms_with_frustum_runs_without_error(self):
        sg=self._three_room_scene(); sg.set_current_room('rb')
        f=Frustum()
        f.update_from_camera(pos=(10,0,1),fwd=(0,1,0),up=(0,0,1),
                              fov_h_deg=60,fov_v_deg=60,near=0.1,far=5.0)
        result=sg.visible_rooms((10,0,1),frustum=f)
        self.assertIsInstance(result,list)

# ── 9. Detect current room ────────────────────────────────────────────────

class TestDetectCurrentRoom(unittest.TestCase):
    def test_exact_aabb(self):
        sg=SceneGraph()
        sg.add_room(_make_room('ra',pos=(0,0,0),bb_min=(-5,-5,0),bb_max=(5,5,3)))
        self.assertEqual(sg.detect_current_room((2,2,1)),'ra')
    def test_fallback_nearest(self):
        sg=SceneGraph()
        sg.add_room(_make_room('ra',pos=(0,0,0)))
        sg.add_room(_make_room('rb',pos=(100,0,0)))
        self.assertEqual(sg.detect_current_room((0,0,10)),'ra')
    def test_empty_scene(self):
        self.assertEqual(SceneGraph().detect_current_room((0,0,0)),'')

# ── 10. SceneGraph objects ────────────────────────────────────────────────

class TestSceneGraphObjects(unittest.TestCase):
    def _scene(self):
        sg=SceneGraph()
        sg.add_room(_make_room('ra',pos=(0,0,0),bb_min=(-10,-10,0),bb_max=(10,10,3)))
        sg.objects.append(SceneObject(obj_type=SceneObjectType.CREATURE,resref='trooper',position=(2,2,0)))
        sg.objects.append(SceneObject(obj_type=SceneObjectType.PLACEABLE,resref='barrel',position=(3,3,0)))
        sg.objects.append(SceneObject(obj_type=SceneObjectType.DOOR,resref='door01',position=(50,50,0)))
        return sg
    def test_by_type(self):
        sg=self._scene()
        self.assertEqual(len(sg.objects_of_type(SceneObjectType.CREATURE)),1)
    def test_near(self):
        sg=self._scene()
        self.assertEqual(len(sg.objects_near((0,0,0),10.0)),2)
    def test_near_excludes_distant(self):
        sg=self._scene()
        self.assertEqual(len(sg.objects_near((0,0,0),1.0)),0)
    def test_assign_to_rooms(self):
        sg=self._scene(); sg.assign_objects_to_rooms()
        c=sg.objects_of_type(SceneObjectType.CREATURE)[0]
        d=sg.objects_of_type(SceneObjectType.DOOR)[0]
        self.assertEqual(c.room_name,'ra')
        self.assertEqual(d.room_name,'')
    def test_objects_in_room(self):
        sg=self._scene(); sg.assign_objects_to_rooms()
        self.assertEqual(len(sg.objects_in_room('ra')),2)

# ── 11. Summary ──────────────────────────────────────────────────────────

class TestSummary(unittest.TestCase):
    def test_name_in_summary(self):
        sg=SceneGraph(); sg.module_name='tar_m01aa'
        self.assertIn('tar_m01aa',sg.summary())
    def test_room_count_in_summary(self):
        sg=SceneGraph()
        for n in ('a','b','c'): sg.add_room(_make_room(n))
        self.assertIn('3 rooms',sg.summary())

# ── 12. SceneManager.build_scene ─────────────────────────────────────────

class TestBuildScene(unittest.TestCase):
    def test_rooms_from_lyt(self):
        mod=_make_module(rooms=_lyt_rooms(('ra',0,0,0),('rb',10,0,0)))
        scene=SceneManager().build_scene(mod)
        self.assertEqual(len(scene.rooms),2)
        self.assertEqual(scene.rooms[0].resref,'ra')
    def test_null_rooms_skipped(self):
        mod=_make_module(rooms=_lyt_rooms(('ra',0,0,0),('NULL',5,0,0),('rb',10,0,0)))
        scene=SceneManager().build_scene(mod)
        self.assertEqual(len(scene.rooms),2)
        self.assertNotIn('null',{r.resref for r in scene.rooms})
    def test_empty_lyt(self):
        self.assertEqual(len(SceneManager().build_scene(_make_module()).rooms),0)
    def test_vis_applied(self):
        mod=_make_module(rooms=_lyt_rooms(('ra',0,0,0),('rb',10,0,0)),
                         vis={'ra':['rb'],'rb':['ra']})
        scene=SceneManager().build_scene(mod)
        self.assertIn('rb',scene.room_by_name('ra').linked_rooms)
    def test_are_props(self):
        are=_make_are_stub(sun_ambient=(100,100,100),sun_fog=1,fog_near=5,fog_far=50)
        mod=_make_module(rooms=_lyt_rooms(('r',0,0,0)),are=are)
        scene=SceneManager().build_scene(mod)
        self.assertEqual(scene.are_props.sun_ambient,(100,100,100))
        self.assertTrue(scene.are_props.fog_enabled)
    def test_git_creatures(self):
        mod=_make_module(rooms=_lyt_rooms(('r',0,0,0)),
                         git=_make_git(creatures=[('soldier',1,2,0)]))
        scene=SceneManager().build_scene(mod)
        c=scene.objects_of_type(SceneObjectType.CREATURE)
        self.assertEqual(len(c),1); self.assertEqual(c[0].resref,'soldier')
    def test_git_placeables(self):
        mod=_make_module(rooms=_lyt_rooms(('r',0,0,0)),
                         git=_make_git(placeables=[('barrel',3,4,0)]))
        scene=SceneManager().build_scene(mod)
        self.assertEqual(len(scene.objects_of_type(SceneObjectType.PLACEABLE)),1)
    def test_git_doors(self):
        mod=_make_module(rooms=_lyt_rooms(('r',0,0,0)),
                         git=_make_git(doors=[('door01','tag1',2,2,0)]))
        scene=SceneManager().build_scene(mod)
        d=scene.objects_of_type(SceneObjectType.DOOR)
        self.assertEqual(len(d),1); self.assertEqual(d[0].tag,'tag1')
    def test_git_waypoints(self):
        mod=_make_module(rooms=_lyt_rooms(('r',0,0,0)),
                         git=_make_git(waypoints=[('wp01','WP_TAG',0,0)]))
        scene=SceneManager().build_scene(mod)
        wps=scene.objects_of_type(SceneObjectType.WAYPOINT)
        self.assertEqual(len(wps),1); self.assertEqual(wps[0].tag,'WP_TAG')
    def test_git_triggers(self):
        mod=_make_module(rooms=_lyt_rooms(('r',0,0,0)),
                         git=_make_git(triggers=[('tr01','tag_tr01')]))
        scene=SceneManager().build_scene(mod)
        self.assertEqual(len(scene.objects_of_type(SceneObjectType.TRIGGER)),1)
    def test_no_lyt(self):
        mod=_make_module(); mod.lyt=None
        self.assertEqual(len(SceneManager().build_scene(mod).rooms),0)
    def test_name_game_preserved(self):
        mod=_make_module(); mod.name='tar_m17ad'; mod.game='K2'
        scene=SceneManager().build_scene(mod)
        self.assertEqual(scene.module_name,'tar_m17ad')
        self.assertEqual(scene.game,'K2')

# ── 13. load_room_models ──────────────────────────────────────────────────

class TestLoadRoomModels(unittest.TestCase):
    def _mdl(self):
        class _M:
            def compute_bounds(self): pass
        m=_M(); m.bb_min=(-3,-3,0); m.bb_max=(3,3,2.5); m.radius=5.0
        return m
    def test_loader_called_for_each(self):
        sg=SceneGraph()
        sg.add_room(_make_room('r1')); sg.add_room(_make_room('r2'))
        called=[]
        count=SceneManager().load_room_models(sg,lambda r:(called.append(r) or self._mdl()))
        self.assertEqual(count,2); self.assertIn('r1',called)
    def test_none_return_counted_missing(self):
        sg=SceneGraph(); sg.add_room(_make_room('r1'))
        self.assertEqual(SceneManager().load_room_models(sg,lambda _:None),0)
    def test_bounds_updated(self):
        sg=SceneGraph()
        room=_make_room('r1',pos=(5,0,0)); sg.add_room(room)
        SceneManager().load_room_models(sg,lambda _:self._mdl())
        self.assertAlmostEqual(room.bb_min[0],-3+5)
        self.assertAlmostEqual(room.bb_max[0], 3+5)
    def test_already_loaded_not_reloaded(self):
        sg=SceneGraph(); room=_make_room('r1'); room.model=object(); sg.add_room(room)
        called=[]
        SceneManager().load_room_models(sg,lambda r:(called.append(r) or None))
        self.assertEqual(len(called),0)

# ── 14. ModelLookup stub ──────────────────────────────────────────────────

class TestModelLookup(unittest.TestCase):
    def test_creature_stub(self):  self.assertEqual(ModelLookup().creature_model('t'),'')
    def test_placeable_stub(self): self.assertEqual(ModelLookup().placeable_model('t'),'')
    def test_door_stub(self):      self.assertEqual(ModelLookup().door_model('t'),'')

# ── 15. Integration ────────────────────────────────────────────────────────

class TestIntegration(unittest.TestCase):
    def test_full_pipeline(self):
        rooms=_lyt_rooms(('m01_entr',0,0,0),('m01_main',30,0,0),('NULL',0,0,0))
        vis={'m01_entr':['m01_main'],'m01_main':['m01_entr']}
        are=_make_are_stub(sun_ambient=(128,64,32),sun_fog=1,
                           fog_near=20,fog_far=80,
                           raw={'Grass_Density':0.5,'Grass_TexName':'gr01'})
        git=_make_git(creatures=[('pc_start',2,2,0)],
                      placeables=[('crate01',5,5,0)])
        mod=_make_module(rooms=rooms,vis=vis,are=are,git=git)
        scene=SceneManager().build_scene(mod)
        self.assertEqual(len(scene.rooms),2)
        self.assertIn('m01_main',scene.room_by_name('m01_entr').linked_rooms)
        self.assertEqual(scene.are_props.sun_ambient,(128,64,32))
        self.assertTrue(scene.are_props.fog_enabled)
        self.assertTrue(scene.are_props.has_grass())
        self.assertEqual(len(scene.objects_of_type(SceneObjectType.CREATURE)),1)
        self.assertEqual(len(scene.objects_of_type(SceneObjectType.PLACEABLE)),1)


if __name__ == '__main__':
    unittest.main()
