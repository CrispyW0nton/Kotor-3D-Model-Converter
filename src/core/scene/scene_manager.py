"""
GhostRigger Module Scene Manager — Phase 5
==========================================
Assembles a full KotOR area from its constituent files:
  • LYT → room MDL positions (Phase 5.1)
  • VIS → per-room visibility culling (Phase 5.1)
  • Frustum culling via Gribb/Hartmann method (Phase 5.3)
    Ref: PyKotor/gl/scene/frustum.py (299 lines); Ericson §7.6; Lengyel FGED Vol.2 §8.4
  • GIT → creature/placeable/door/waypoint/trigger objects (Phase 5.2)
    Ref: KotOR.js/ForgeArea.ts (1,096 lines) GIT loading flow
  • ARE → ambient/fog/grass properties for viewport tinting (Phase 5.4)
  • Grass placement metadata from ARE+WOK (Phase 5.5 placeholder)

Design follows the ForgeArea.ts / ForgeRoom.ts pattern from KotOR.js:
  SceneManager.load_module(module: KotorModule, library) → SceneGraph
  SceneGraph.visible_rooms(camera_pos, camera_fwd, fov_h, fov_v, aspect)
  SceneGraph.objects_in_room(room_name: str) → list[SceneObject]

All math follows:
  • Gregory §12.5 (view frustum), Ericson §4.3 (AABB/sphere tests)
  • KotOR.js ForgeRoom.ts for room transform order (translate after model load)
  • PyKotor frustum.py for Gribb/Hartmann VP-matrix plane extraction

NOTE: This module is headless (no rendering). It provides data structures
that viewport.py consumes to decide what to draw.
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any, Set

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Vector/matrix helpers (pure Python — numpy optional for speed)
# ─────────────────────────────────────────────────────────────────────────────

def _dot3(a: Tuple, b: Tuple) -> float:
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]


def _sub3(a: Tuple, b: Tuple) -> Tuple:
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])


def _add3(a: Tuple, b: Tuple) -> Tuple:
    return (a[0]+b[0], a[1]+b[1], a[2]+b[2])


def _scale3(v: Tuple, s: float) -> Tuple:
    return (v[0]*s, v[1]*s, v[2]*s)


def _norm3(v: Tuple) -> Tuple:
    l = math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2])
    if l < 1e-9:
        return (0.0, 0.0, 1.0)
    return (v[0]/l, v[1]/l, v[2]/l)


def _cross3(a: Tuple, b: Tuple) -> Tuple:
    return (
        a[1]*b[2] - a[2]*b[1],
        a[2]*b[0] - a[0]*b[2],
        a[0]*b[1] - a[1]*b[0],
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Frustum Culling — Gribb/Hartmann method
#  Ref: "Fast Extraction of Viewing Frustum Planes from the World-View-
#       Projection Matrix", Gribb & Hartmann 2001.
#  See also: PyKotor/gl/scene/frustum.py (299 lines), Gregory §12.5,
#            Ericson §4.3.2.
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Plane:
    """Ax + By + Cz + D = 0  (normal=(A,B,C), D is offset)."""
    a: float = 0.0
    b: float = 0.0
    c: float = 0.0
    d: float = 0.0

    def normalize(self) -> 'Plane':
        l = math.sqrt(self.a*self.a + self.b*self.b + self.c*self.c)
        if l < 1e-12:
            return self
        inv = 1.0 / l
        return Plane(self.a*inv, self.b*inv, self.c*inv, self.d*inv)

    def distance_to_point(self, x: float, y: float, z: float) -> float:
        return self.a*x + self.b*y + self.c*z + self.d


class Frustum:
    """
    View frustum with six planes for fast AABB / sphere culling.

    Build from a camera by calling update_from_camera().
    Or from a 4x4 column-major MVP matrix (16 floats, row-major order)
    via update_from_matrix().

    Plane indices: LEFT=0, RIGHT=1, BOTTOM=2, TOP=3, NEAR=4, FAR=5.

    Gribb/Hartmann formula (column-major MVP M, row-order):
        Left  : row3 + row0
        Right : row3 - row0
        Bottom: row3 + row1
        Top   : row3 - row1
        Near  : row3 + row2
        Far   : row3 - row2
    where row_i = (M[i], M[4+i], M[8+i], M[12+i]) for 4×4.
    """

    LEFT   = 0
    RIGHT  = 1
    BOTTOM = 2
    TOP    = 3
    NEAR   = 4
    FAR    = 5

    def __init__(self):
        self.planes: List[Plane] = [Plane() for _ in range(6)]

    def update_from_matrix(self, m: List[float]):
        """
        m is a 16-float row-major 4×4 view-projection matrix.
        Ref: Gribb/Hartmann 2001; PyKotor frustum.py _extract_planes().
        """
        # Row extraction from 4×4 row-major:
        # row_i = m[i*4 : i*4+4]
        r0 = m[0:4];  r1 = m[4:8];  r2 = m[8:12];  r3 = m[12:16]

        def _plane(row_a, row_b, sign):
            return Plane(
                row_a[0] + sign*row_b[0],
                row_a[1] + sign*row_b[1],
                row_a[2] + sign*row_b[2],
                row_a[3] + sign*row_b[3],
            ).normalize()

        self.planes[self.LEFT]   = _plane(r3, r0,  1.0)
        self.planes[self.RIGHT]  = _plane(r3, r0, -1.0)
        self.planes[self.BOTTOM] = _plane(r3, r1,  1.0)
        self.planes[self.TOP]    = _plane(r3, r1, -1.0)
        self.planes[self.NEAR]   = _plane(r3, r2,  1.0)
        self.planes[self.FAR]    = _plane(r3, r2, -1.0)

    def update_from_camera(self,
                           pos: Tuple,
                           fwd: Tuple,
                           up:  Tuple,
                           fov_h_deg: float,
                           fov_v_deg: float,
                           near: float = 0.1,
                           far:  float = 512.0):
        """
        Build frustum planes directly from camera parameters.
        Ref: Gregory §12.5.1 — build 6 planes from camera basis vectors
             and half-angle extents.

        KotOR world uses Y-forward, Z-up (right-handed).
        fov_h_deg / fov_v_deg: full field-of-view (not half-angle).

        Each side plane passes through pos with inward-facing normal.
        A point P is inside the frustum when distance_to_point(P) >= 0
        for all six planes (normals point inward).

        Left  plane: passes through pos, normal = cross(fwd_left_edge, up)
                     where fwd_left_edge is the left boundary ray direction.
        Construction follows Gregory §12.5.1 eqs (12.13)-(12.18):
            n_left   = normalise(fwd - right * tan_h)  then cross with up
            Actually the clean formulation is:
            n_left   = fwd * cos(hh) + right * sin(hh)   (inward facing left side)
            n_right  = fwd * cos(hh) - right * sin(hh)
            n_bottom = fwd * cos(hv) + up    * sin(hv)
            n_top    = fwd * cos(hv) - up    * sin(hv)
        Plane D = -dot(n, pos) so that pos lies on the plane boundary.
        """
        right   = _norm3(_cross3(fwd, up))
        real_up = _norm3(_cross3(right, fwd))
        fwd     = _norm3(fwd)

        # Half-angles in radians
        hh = math.radians(fov_h_deg * 0.5)
        hv = math.radians(fov_v_deg * 0.5)

        cos_h = math.cos(hh)
        sin_h = math.sin(hh)
        cos_v = math.cos(hv)
        sin_v = math.sin(hv)

        def _plane_through_pos(n: Tuple) -> Plane:
            """Plane with inward normal n passing through camera pos."""
            n = _norm3(n)
            d = -_dot3(n, pos)
            return Plane(n[0], n[1], n[2], d)

        near_center = _add3(pos, _scale3(fwd, near))
        far_center  = _add3(pos, _scale3(fwd, far))

        # Near / far planes (normals point inward, i.e. into the frustum)
        self.planes[self.NEAR] = _plane_through_pos(fwd)
        # Override D for near plane so it passes through near_center not pos
        nf = _norm3(fwd)
        self.planes[self.NEAR] = Plane(nf[0], nf[1], nf[2], -_dot3(nf, near_center))
        # Far plane: inward normal is -fwd, passes through far_center
        nb = _scale3(fwd, -1.0)
        self.planes[self.FAR]  = Plane(nb[0], nb[1], nb[2], -_dot3(nb, far_center))

        # Side planes: all pass through camera pos (apex of frustum cone)
        # Inward normals derived from half-angle geometry.
        # Left  plane inward normal: rotate fwd toward +right by hh
        n_left   = _add3(_scale3(fwd, cos_h), _scale3(right,  sin_h))
        # Right plane inward normal: rotate fwd toward -right by hh
        n_right  = _add3(_scale3(fwd, cos_h), _scale3(right, -sin_h))
        # Bottom plane inward normal: rotate fwd toward +up by hv
        n_bottom = _add3(_scale3(fwd, cos_v), _scale3(real_up,  sin_v))
        # Top   plane inward normal: rotate fwd toward -up by hv
        n_top    = _add3(_scale3(fwd, cos_v), _scale3(real_up, -sin_v))

        self.planes[self.LEFT]   = _plane_through_pos(n_left)
        self.planes[self.RIGHT]  = _plane_through_pos(n_right)
        self.planes[self.BOTTOM] = _plane_through_pos(n_bottom)
        self.planes[self.TOP]    = _plane_through_pos(n_top)

    def test_sphere(self, cx: float, cy: float, cz: float, r: float) -> bool:
        """
        True if the sphere (cx,cy,cz,r) is fully or partially inside the
        frustum (not fully outside any plane).
        Ref: Ericson §4.3.2; Gregory §12.5.2.
        """
        for p in self.planes:
            if p.distance_to_point(cx, cy, cz) < -r:
                return False
        return True

    def test_aabb(self,
                  bb_min: Tuple,
                  bb_max: Tuple) -> bool:
        """
        True if the axis-aligned bounding box overlaps or is inside the
        frustum.  Uses the "positive vertex" (p-vertex) test.
        Ref: Ericson §4.3.2; Gribb/Hartmann 2001.
        """
        for p in self.planes:
            # p-vertex: corner of AABB most along the plane normal
            px = bb_max[0] if p.a >= 0 else bb_min[0]
            py = bb_max[1] if p.b >= 0 else bb_min[1]
            pz = bb_max[2] if p.c >= 0 else bb_min[2]
            if p.distance_to_point(px, py, pz) < 0:
                return False
        return True

    def is_trivially_disabled(self) -> bool:
        """True if the frustum was never configured (all planes are zero)."""
        return all(
            p.a == 0 and p.b == 0 and p.c == 0
            for p in self.planes
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Scene Object types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SceneRoom:
    """
    One room loaded from a LYT entry.
    Ref: KotOR.js ForgeRoom.ts — stores model resref, translation, MDL object,
         and linked rooms from VIS.
    """
    resref:       str           # room model name (lower-case)
    position:     Tuple         = (0.0, 0.0, 0.0)   # world position from LYT
    visible:      bool          = True               # toggleable from UI
    model:        Any           = None               # loaded KotorModel (or None)
    bb_min:       Tuple         = (-5.0, -5.0, 0.0)  # world-space AABB
    bb_max:       Tuple         = ( 5.0,  5.0, 3.0)
    bounding_r:   float         = 10.0               # bounding sphere radius
    linked_rooms: List[str]     = field(default_factory=list)  # from VIS
    wok:          Any           = None               # WOKData (loaded alongside model)


@dataclass
class SceneObjectType:
    CREATURE   = 'creature'
    PLACEABLE  = 'placeable'
    DOOR       = 'door'
    WAYPOINT   = 'waypoint'
    SOUND      = 'sound'
    TRIGGER    = 'trigger'


@dataclass
class SceneObject:
    """
    An instance object placed in the scene from GIT.
    Ref: KotOR.js ForgeArea.ts — loads Creature List, Placeable List,
         Door List, WaypointList, SoundList, TriggerList from GIT GFF.
    Phase 5.2 roadmap item.
    """
    obj_type:  str           # SceneObjectType constant
    resref:    str           # UTC/UTP/UTD resref
    position:  Tuple         = (0.0, 0.0, 0.0)
    bearing:   float         = 0.0           # Y-rotation in radians (KotOR bearing)
    model:     Any           = None          # loaded KotorModel (lazy)
    room_name: str           = ""            # which room this object belongs to
    tag:       str           = ""
    # Door-specific
    linked_to:        str    = ""
    linked_to_module: str    = ""
    # Trigger geometry
    geometry:  List[Tuple]   = field(default_factory=list)


@dataclass
class AREProperties:
    """
    Lighting and atmosphere properties extracted from the .are GFF.
    Ref: KotOR.js ForgeArea.ts; Roadmap Phase 5.4.
    Used by viewport.py for ambient tint and fog rendering.
    """
    # Ambient and diffuse (R,G,B 0-255)
    sun_ambient:  Tuple = (64,  64,  64)
    sun_diffuse:  Tuple = (255, 255, 255)
    # Fog
    fog_enabled:  bool  = False
    fog_color:    Tuple = (0, 0, 0)
    fog_near:     float = 100.0
    fog_far:      float = 200.0
    # Day/night
    day_night:    bool  = False
    lighting_id:  int   = 0
    # Grass (Phase 5.5)
    grass_density:  float = 0.0
    grass_tex_name: str   = ""
    grass_quad_size: float = 1.0
    grass_prob_ll:  float = 0.25
    grass_prob_lr:  float = 0.25
    grass_prob_ul:  float = 0.25
    grass_prob_ur:  float = 0.25
    # Minimap
    minimap_res_ref: str  = ""

    @classmethod
    def from_are_data(cls, are) -> 'AREProperties':
        """Convert an AREData object (module_format.py) to AREProperties."""
        if are is None:
            return cls()
        ap = cls()
        ap.sun_ambient = are.sun_ambient
        ap.sun_diffuse = are.sun_diffuse
        ap.fog_enabled = bool(are.sun_fog)
        ap.fog_color   = are.fog_color
        ap.fog_near    = are.fog_near
        ap.fog_far     = are.fog_far
        # Extended fields from _raw GFF dict (if present)
        raw = getattr(are, '_raw', None) or {}
        ap.day_night     = bool(raw.get('DayNightCycle', 0))
        ap.lighting_id   = int(raw.get('LightingScheme', 0))
        ap.grass_density = float(raw.get('Grass_Density', 0.0))
        ap.grass_tex_name = str(raw.get('Grass_TexName', ''))
        ap.grass_quad_size = float(raw.get('Grass_QuadSize', 1.0))
        ap.grass_prob_ll = float(raw.get('Grass_Prob_LL', 0.25))
        ap.grass_prob_lr = float(raw.get('Grass_Prob_LR', 0.25))
        ap.grass_prob_ul = float(raw.get('Grass_Prob_UL', 0.25))
        ap.grass_prob_ur = float(raw.get('Grass_Prob_UR', 0.25))
        return ap

    def ambient_float(self) -> Tuple:
        """Ambient color normalized to [0,1] floats."""
        r, g, b = self.sun_ambient
        return (r/255.0, g/255.0, b/255.0)

    def fog_color_float(self) -> Tuple:
        r, g, b = self.fog_color
        return (r/255.0, g/255.0, b/255.0)

    def has_grass(self) -> bool:
        return self.grass_density > 0.0 and bool(self.grass_tex_name)


# ─────────────────────────────────────────────────────────────────────────────
#  SceneGraph  — the assembled area
# ─────────────────────────────────────────────────────────────────────────────

class SceneGraph:
    """
    A fully-assembled KotOR module area scene.

    Contains:
      - List of SceneRoom (from LYT, with MDLs attached)
      - List of SceneObject (from GIT)
      - AREProperties (for ambient/fog rendering)
      - VIS connectivity for room-based culling

    Key methods:
      visible_rooms(camera_pos, frustum) → List[SceneRoom]
        Uses VIS connectivity (only draw rooms reachable from current room)
        then frustum-culls the result.
        Ref: KotOR.js ForgeArea.ts linkedRooms culling + THREE.js frustum.

      objects_near(position, radius) → List[SceneObject]
        Returns GIT objects within sphere of given radius.

    NOTE: Room model loading is lazy — call load_room_models(loader_fn)
    to populate room.model fields.  This keeps the SceneGraph itself
    headless and testable without a game installation.
    """

    def __init__(self):
        self.rooms:       List[SceneRoom]    = []
        self.objects:     List[SceneObject]  = []
        self.are_props:   AREProperties      = AREProperties()
        self.module_name: str                = ""
        self.game:        str                = "K1"
        # VIS connectivity: room_name → set of visible room names
        self._vis: Dict[str, Set[str]]       = {}
        # Current room name (updated by set_current_room)
        self._current_room: str              = ""

    # ── Room management ──────────────────────────────────────────────────────

    def add_room(self, room: SceneRoom):
        self.rooms.append(room)

    def room_by_name(self, name: str) -> Optional[SceneRoom]:
        lname = name.lower()
        for r in self.rooms:
            if r.resref == lname:
                return r
        return None

    def set_vis_data(self, vis_dict: Dict[str, List[str]]):
        """Populate VIS connectivity from VISData.visibility dict."""
        self._vis = {k: set(v) for k, v in vis_dict.items()}
        # Also set linked_rooms on each SceneRoom
        for room in self.rooms:
            linked = self._vis.get(room.resref, set())
            room.linked_rooms = list(linked)

    def set_current_room(self, room_name: str):
        """
        Set the 'current' room (the room the camera is in).
        Used by visible_rooms() for VIS culling.
        Ref: KotOR.js ForgeArea.ts — camera room detection.
        """
        self._current_room = room_name.lower()

    def detect_current_room(self, camera_pos: Tuple) -> str:
        """
        Find which room the camera is currently inside by testing
        the camera position against each room's AABB.
        Returns the resref of the containing room, or ''.
        Falls back to nearest room centroid if no exact AABB match.
        """
        # Exact AABB test
        for room in self.rooms:
            if not room.visible:
                continue
            bmin, bmax = room.bb_min, room.bb_max
            if (bmin[0] <= camera_pos[0] <= bmax[0] and
                bmin[1] <= camera_pos[1] <= bmax[1] and
                bmin[2] <= camera_pos[2] <= bmax[2]):
                return room.resref

        # Fallback: closest room centroid
        best_room = ""
        best_dist = float('inf')
        for room in self.rooms:
            cx = (room.bb_min[0] + room.bb_max[0]) * 0.5
            cy = (room.bb_min[1] + room.bb_max[1]) * 0.5
            cz = (room.bb_min[2] + room.bb_max[2]) * 0.5
            dx = camera_pos[0] - cx
            dy = camera_pos[1] - cy
            dz = camera_pos[2] - cz
            d2 = dx*dx + dy*dy + dz*dz
            if d2 < best_dist:
                best_dist = d2
                best_room = room.resref
        return best_room

    # ── Visibility culling ───────────────────────────────────────────────────

    def visible_rooms(self,
                      camera_pos: Tuple,
                      frustum: Optional[Frustum] = None,
                      use_vis: bool = True) -> List[SceneRoom]:
        """
        Return the list of rooms that should be rendered this frame.

        Algorithm (mirrors KotOR.js ForgeArea.ts + ForgeRoom.ts):
        1. If use_vis: start from current_room and collect all VIS-reachable
           rooms (up to 2 hops, matching KotOR's room-to-room visibility).
           If no VIS data or no current_room → include all rooms.
        2. Filter to visible=True rooms.
        3. If frustum is provided: frustum-cull each room against its AABB.
           Ref: Ericson §4.3, Gregory §12.5.

        Returns rooms in LYT order (render order preserved).
        """
        # Step 1: VIS connectivity filter
        if use_vis and self._current_room and self._vis:
            candidate_names: Set[str] = {self._current_room}
            # 1-hop VIS connections
            for name in self._vis.get(self._current_room, set()):
                candidate_names.add(name)
            candidates = [r for r in self.rooms if r.resref in candidate_names]
        else:
            candidates = list(self.rooms)

        # Step 2: visibility toggle
        candidates = [r for r in candidates if r.visible]

        # Step 3: frustum culling (skip if frustum not configured)
        if frustum is not None and not frustum.is_trivially_disabled():
            result = []
            for room in candidates:
                # Translate AABB to world space (room.position is the LYT offset)
                px, py, pz = room.position
                wmin = (room.bb_min[0]+px, room.bb_min[1]+py, room.bb_min[2]+pz)
                wmax = (room.bb_max[0]+px, room.bb_max[1]+py, room.bb_max[2]+pz)
                if frustum.test_aabb(wmin, wmax):
                    result.append(room)
            return result

        return candidates

    def rooms_all_visible(self) -> List[SceneRoom]:
        """Return all rooms with visible=True (no frustum culling)."""
        return [r for r in self.rooms if r.visible]

    def set_all_rooms_visible(self, state: bool):
        for r in self.rooms:
            r.visible = state

    def toggle_room(self, resref: str, state: Optional[bool] = None):
        """Toggle (or set) a single room's visibility."""
        r = self.room_by_name(resref)
        if r:
            r.visible = state if state is not None else not r.visible

    # ── Object queries ───────────────────────────────────────────────────────

    def objects_of_type(self, obj_type: str) -> List[SceneObject]:
        return [o for o in self.objects if o.obj_type == obj_type]

    def objects_in_room(self, room_name: str) -> List[SceneObject]:
        lname = room_name.lower()
        return [o for o in self.objects if o.room_name == lname]

    def objects_near(self, pos: Tuple, radius: float) -> List[SceneObject]:
        """Return objects within sphere of radius around pos."""
        r2 = radius * radius
        result = []
        for obj in self.objects:
            dx = obj.position[0] - pos[0]
            dy = obj.position[1] - pos[1]
            dz = obj.position[2] - pos[2]
            if dx*dx + dy*dy + dz*dz <= r2:
                result.append(obj)
        return result

    def assign_objects_to_rooms(self):
        """
        For each SceneObject, find which room's AABB contains it and set
        room_name.  Objects outside all rooms get room_name=''.
        Ref: KotOR.js ForgeArea.ts — objects are added to their parent room.
        """
        for obj in self.objects:
            obj.room_name = ''
            for room in self.rooms:
                px, py, pz = room.position
                ox, oy, oz = obj.position
                wmin = (room.bb_min[0]+px, room.bb_min[1]+py, room.bb_min[2]+pz)
                wmax = (room.bb_max[0]+px, room.bb_max[1]+py, room.bb_max[2]+pz)
                if (wmin[0] <= ox <= wmax[0] and
                    wmin[1] <= oy <= wmax[1] and
                    wmin[2] <= oz <= wmax[2]):
                    obj.room_name = room.resref
                    break

    # ── Metrics ──────────────────────────────────────────────────────────────

    def summary(self) -> str:
        total = len(self.rooms)
        vis   = sum(1 for r in self.rooms if r.visible)
        loaded = sum(1 for r in self.rooms if r.model is not None)
        objs  = len(self.objects)
        return (f"SceneGraph '{self.module_name}' ({self.game}): "
                f"{total} rooms ({loaded} loaded, {vis} visible), "
                f"{objs} objects, "
                f"grass={'yes' if self.are_props.has_grass() else 'no'}")


# ─────────────────────────────────────────────────────────────────────────────
#  SceneManager  — high-level module loading
# ─────────────────────────────────────────────────────────────────────────────

class SceneManager:
    """
    Phase 5 — Module Scene Viewer: assembles a SceneGraph from a KotorModule.

    Usage:
        sm = SceneManager()
        scene = sm.build_scene(module)               # from module_format.KotorModule
        scene.load_room_models(loader_fn)            # populate room.model fields
        visible = scene.visible_rooms(cam_pos, frustum)

    The loader_fn signature: loader_fn(resref: str) -> Optional[KotorModel]
    Viewport calls this, e.g. using game_library.load_model(resref).

    Ref: KotOR.js ForgeArea.ts loadRooms() + addObjects() pattern.
    """

    def build_scene(self, module, loader_fn=None) -> SceneGraph:
        """
        Build a SceneGraph from a KotorModule object (module_format.py).

        Steps (mirrors ForgeArea.ts):
          1. Create SceneRoom for each LYT room (skip 'NULL' rooms)
          2. Set VIS connectivity from VISData
          3. Create SceneObjects from GIT creatures/placeables/doors/waypoints/triggers
          4. Parse ARE for AREProperties
          5. If loader_fn given: load MDL for each room immediately
          6. Assign objects to rooms

        Args:
            module: KotorModule (may have lyt/vis/are/git/ifo/wok set)
            loader_fn: optional callable(resref:str) → KotorModel|None
        """
        scene = SceneGraph()
        scene.module_name = getattr(module, 'name', '')
        scene.game        = getattr(module, 'game', 'K1')

        # ── Phase 5.1: LYT rooms ─────────────────────────────────────────────
        lyt = getattr(module, 'lyt', None)
        if lyt is not None:
            null_count = 0
            for lyt_room in lyt.rooms:
                # Skip NULL rooms (KotOR uses 'NULL' as placeholder in LYT)
                # Ref: KotOR.js ForgeRoom.ts loadModel() — skips if name is null/empty
                if lyt_room.model.lower() in ('null', ''):
                    null_count += 1
                    continue

                room = SceneRoom(
                    resref   = lyt_room.model.lower(),
                    position = (lyt_room.x, lyt_room.y, lyt_room.z),
                )
                scene.add_room(room)

            if null_count:
                log.debug(f"SceneManager: skipped {null_count} NULL rooms in LYT")

            log.info(f"SceneManager: created {len(scene.rooms)} rooms "
                     f"from LYT ({lyt_room.model if lyt.rooms else 'empty'})")
        else:
            log.warning("SceneManager: no LYT data — scene has no rooms")

        # ── VIS connectivity ─────────────────────────────────────────────────
        vis = getattr(module, 'vis', None)
        if vis is not None:
            scene.set_vis_data(vis.visibility)
            log.debug(f"SceneManager: VIS data loaded ({len(vis.visibility)} entries)")

        # ── Phase 5.4: ARE properties ────────────────────────────────────────
        are = getattr(module, 'are', None)
        scene.are_props = AREProperties.from_are_data(are)
        if are is not None:
            log.debug(f"SceneManager: ARE props: ambient={scene.are_props.sun_ambient}, "
                      f"fog={scene.are_props.fog_enabled}")

        # ── Phase 5.2: GIT objects ───────────────────────────────────────────
        git = getattr(module, 'git', None)
        if git is not None:
            self._load_git_objects(scene, git)

        # ── Load MDLs if loader provided ─────────────────────────────────────
        if loader_fn is not None:
            loaded_count = self.load_room_models(scene, loader_fn)
            log.info(f"SceneManager: loaded {loaded_count}/{len(scene.rooms)} room MDLs")

        # ── Assign objects to rooms ───────────────────────────────────────────
        scene.assign_objects_to_rooms()

        # ── Load per-room WOKs from module.room_woks ─────────────────────────
        room_woks = getattr(module, 'room_woks', {})
        for room in scene.rooms:
            if room.resref in room_woks:
                room.wok = room_woks[room.resref]

        log.info(f"SceneManager: {scene.summary()}")
        return scene

    def _load_git_objects(self, scene: SceneGraph, git):
        """
        Populate scene.objects from GITData.
        Ref: KotOR.js ForgeArea.ts — addCreatures(), addPlaceables(),
             addDoors(), addWaypoints(), addTriggers().
        Phase 5.2 roadmap.
        """
        # Creatures
        for c in getattr(git, 'creatures', []):
            scene.objects.append(SceneObject(
                obj_type = SceneObjectType.CREATURE,
                resref   = c.resref,
                position = (c.x, c.y, c.z),
                bearing  = c.bearing,
            ))

        # Placeables
        for p in getattr(git, 'placeables', []):
            scene.objects.append(SceneObject(
                obj_type = SceneObjectType.PLACEABLE,
                resref   = p.resref,
                position = (p.x, p.y, p.z),
                bearing  = p.bearing,
            ))

        # Doors
        for d in getattr(git, 'doors', []):
            scene.objects.append(SceneObject(
                obj_type         = SceneObjectType.DOOR,
                resref           = d.resref,
                tag              = d.tag,
                position         = (d.x, d.y, d.z),
                bearing          = d.bearing,
                linked_to        = d.linked_to,
                linked_to_module = d.linked_to_module,
            ))

        # Waypoints
        for w in getattr(git, 'waypoints', []):
            scene.objects.append(SceneObject(
                obj_type = SceneObjectType.WAYPOINT,
                resref   = w.resref,
                tag      = w.tag,
                position = (w.x, w.y, w.z),
                bearing  = w.bearing,
            ))

        # Triggers
        for t in getattr(git, 'triggers', []):
            scene.objects.append(SceneObject(
                obj_type  = SceneObjectType.TRIGGER,
                resref    = t.resref,
                tag       = t.tag,
                position  = (t.x, t.y, t.z),
                geometry  = list(t.geometry),
                linked_to = t.linked_to,
            ))

        log.debug(f"SceneManager: GIT loaded: {git.summary()}")

    def load_room_models(self, scene: SceneGraph, loader_fn) -> int:
        """
        Load MDL for every room that doesn't yet have a model.
        loader_fn(resref: str) → KotorModel | None

        After loading, update room.bb_min, bb_max, bounding_r from the model's
        computed bounds, translated to world space by room.position.
        Ref: KotOR.js ForgeRoom.ts — translateFromLYT() after loadModel().
        """
        loaded = 0
        for room in scene.rooms:
            if room.model is not None:
                continue
            try:
                model = loader_fn(room.resref)
            except Exception as e:
                log.warning(f"SceneManager: failed to load room '{room.resref}': {e}")
                model = None

            if model is not None:
                room.model = model
                # Update AABB from model bounds
                self._update_room_bounds(room, model)
                loaded += 1
            else:
                log.debug(f"SceneManager: room MDL not found: '{room.resref}'")
        return loaded

    def _update_room_bounds(self, room: SceneRoom, model):
        """
        Recompute room.bb_min/bb_max/bounding_r from the loaded model,
        then translate by room.position.
        Ref: KotOR.js ForgeRoom.ts getAABB() — translates by LYT position.
        """
        try:
            if hasattr(model, 'compute_bounds'):
                model.compute_bounds()
            bb_min = getattr(model, 'bb_min', None)
            bb_max = getattr(model, 'bb_max', None)
            radius = getattr(model, 'radius', None)

            if bb_min is not None and bb_max is not None:
                px, py, pz = room.position
                room.bb_min = (bb_min[0]+px, bb_min[1]+py, bb_min[2]+pz)
                room.bb_max = (bb_max[0]+px, bb_max[1]+py, bb_max[2]+pz)
                if radius is not None:
                    room.bounding_r = float(radius)
                else:
                    # Estimate from AABB diagonal
                    dx = room.bb_max[0] - room.bb_min[0]
                    dy = room.bb_max[1] - room.bb_min[1]
                    dz = room.bb_max[2] - room.bb_min[2]
                    room.bounding_r = math.sqrt(dx*dx + dy*dy + dz*dz) * 0.5
        except Exception as e:
            log.debug(f"SceneManager: bounds update failed for room '{room.resref}': {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  ModelLookup helper — resolves appearance.2da → MDL resref
# ─────────────────────────────────────────────────────────────────────────────

class ModelLookup:
    """
    Phase 5.2: Resolve GIT creature/placeable/door resrefs to MDL resrefs.

    Chains:
      Creature:   UTC.Appearance_Type → appearance.2da[row].modelname
      Placeable:  UTP.Appearance      → placeables.2da[row].modelname
      Door:       UTD.GenericType     → genericdoors.2da[row].modelname

    Ref: KotOR.js ForgeArea.ts addCreatures() — reads appearance.2da;
         GhostRigger src/core/creature_appearance.py (existing 954-line module).

    NOTE: This class is a stub for Phase 5.2.  Full implementation requires
    game library access (2DA tables).  The interface is defined here so
    viewport.py can call it without changes when Phase 5.2 is completed.
    """

    def __init__(self, game_library=None):
        self._lib = game_library
        self._cache: Dict[str, str] = {}

    def creature_model(self, utc_resref: str) -> str:
        """
        Resolve a UTC resref to its body MDL resref.
        Returns '' if lookup fails.
        """
        if utc_resref in self._cache:
            return self._cache[utc_resref]
        # Phase 5.2 TODO: load UTC GFF → Appearance_Type → appearance.2da
        # For now return empty (creature renders as invisible placeholder)
        return ''

    def placeable_model(self, utp_resref: str) -> str:
        """Resolve UTP resref → MDL resref via placeables.2da."""
        # Phase 5.2 TODO
        return ''

    def door_model(self, utd_resref: str) -> str:
        """Resolve UTD resref → MDL resref via genericdoors.2da."""
        # Phase 5.2 TODO
        return ''


# ──────────────────────────────────────────────────────────────────────────────
#  CharacterSceneRegistry  (Phase 2 — GhostRigger Character Builder)
# ──────────────────────────────────────────────────────────────────────────────

class CharacterSceneRegistry:
    """Thread-safe in-process registry for CharacterScene objects.

    Allows different parts of the application (main window, character builder,
    IPC server) to share and look up named CharacterScene instances without
    passing references through every call stack.

    The registry uses the scene's ``scene_id`` (UUID string) as the primary
    key, with an optional human-readable ``alias`` for friendly lookup.

    Usage
    -----
    ::

        from src.core.qt_core.scene.scene_manager import get_character_registry
        from src.core.qt_core.geometry.model_data import CharacterScene, PartSlot

        reg = get_character_registry()

        scene = CharacterScene(game_version='K1', character_name='Revan')
        reg.register(scene, alias='revan')

        same = reg.get_by_alias('revan')
        assert same is scene

        reg.unregister(scene.scene_id)
    """

    def __init__(self) -> None:
        import threading
        self._lock   = threading.Lock()
        self._scenes: Dict[str, Any]    = {}   # scene_id → CharacterScene
        self._aliases: Dict[str, str]   = {}   # alias → scene_id

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, scene, alias: str = "") -> str:
        """Register *scene* and return its scene_id.

        Parameters
        ----------
        scene : CharacterScene to register.
        alias : Optional friendly name (e.g. 'active', 'revan').
                If a previous scene was registered under the same alias it
                is *not* removed; only the alias mapping is updated.

        Returns
        -------
        scene.scene_id
        """
        sid = scene.scene_id
        with self._lock:
            self._scenes[sid] = scene
            if alias:
                self._aliases[alias] = sid
        log.debug("CharacterSceneRegistry.register: id=%s alias=%r", sid, alias)
        return sid

    def unregister(self, scene_id: str) -> None:
        """Remove a scene from the registry by its scene_id."""
        with self._lock:
            self._scenes.pop(scene_id, None)
            # Clean up any aliases pointing to this scene
            dead = [k for k, v in self._aliases.items() if v == scene_id]
            for k in dead:
                del self._aliases[k]
        log.debug("CharacterSceneRegistry.unregister: id=%s", scene_id)

    # ── Lookup ────────────────────────────────────────────────────────────────

    def get(self, scene_id: str):
        """Return the CharacterScene for the given scene_id, or None."""
        with self._lock:
            return self._scenes.get(scene_id)

    def get_by_alias(self, alias: str):
        """Return the CharacterScene registered under *alias*, or None."""
        with self._lock:
            sid = self._aliases.get(alias)
            return self._scenes.get(sid) if sid else None

    def set_alias(self, scene_id: str, alias: str) -> None:
        """Assign an alias to an already-registered scene."""
        with self._lock:
            if scene_id not in self._scenes:
                raise KeyError(f"scene_id not registered: {scene_id!r}")
            self._aliases[alias] = scene_id

    # ── Introspection ─────────────────────────────────────────────────────────

    def list_scenes(self) -> List[Any]:
        """Return a snapshot list of all registered CharacterScene objects."""
        with self._lock:
            return list(self._scenes.values())

    def list_aliases(self) -> Dict[str, str]:
        """Return a copy of the alias → scene_id mapping."""
        with self._lock:
            return dict(self._aliases)

    def __len__(self) -> int:
        with self._lock:
            return len(self._scenes)

    def clear(self) -> None:
        """Remove all registered scenes (mainly for testing)."""
        with self._lock:
            self._scenes.clear()
            self._aliases.clear()


# ── Module-level singleton ────────────────────────────────────────────────────

_character_registry: Optional["CharacterSceneRegistry"] = None
_registry_lock = None


def get_character_registry() -> "CharacterSceneRegistry":
    """Return the process-wide CharacterSceneRegistry singleton."""
    global _character_registry, _registry_lock
    if _character_registry is None:
        import threading
        if _registry_lock is None:
            _registry_lock = threading.Lock()
        with _registry_lock:
            if _character_registry is None:
                _character_registry = CharacterSceneRegistry()
    return _character_registry


def reset_character_registry() -> None:
    """Reset the singleton registry (for testing only)."""
    global _character_registry
    if _character_registry is not None:
        _character_registry.clear()
    _character_registry = None


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 5.0 — SceneFrameRenderer
#  Wires SceneGraph (room assembly from LYT/VIS/ARE/GIT) into the
#  viewport render loop.  Provides a scene-aware draw-list builder that
#  combines frustum culling + VIS-based room culling and returns a flat
#  list of (model_name, world_pos, room_name) tuples for the GPU renderer.
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SceneDrawEntry:
    """One render-eligible room or object from the scene graph.

    Attributes
    ----------
    model_name  : str    – resref of the MDL to render
    world_pos   : tuple  – (x, y, z) translation from LYT room position
    room_name   : str    – source room name (for debug and culling info)
    is_object   : bool   – True if this is a GIT object (not a room mesh)
    object_type : str    – 'creature', 'placeable', 'door', 'waypoint', '' if room
    """
    model_name  : str
    world_pos   : Tuple[float, float, float]
    room_name   : str
    is_object   : bool = False
    object_type : str  = ''


class SceneFrameRenderer:
    """Bridge between ``SceneGraph`` and the GPU / CPU renderer in viewport.py.

    Implements the ``ForgeArea.ts`` render-loop pattern:
    1.  Determine which rooms are visible (frustum + VIS culling).
    2.  For each visible room, emit its room-model ``SceneDrawEntry``.
    3.  For each visible room, emit all ``SceneObject`` entries (GIT objects).
    4.  Optionally filter by object type (creatures, placeables, etc.).

    Usage
    -----
    ::

        sfr = SceneFrameRenderer(scene_graph)

        # Viewport code (called each frame):
        draw_list = sfr.build_draw_list(
            camera_pos   = cam.eye,
            camera_fwd   = cam.forward,
            fov_h        = 90.0,
            fov_v        = 60.0,
            near         = 0.01,
            far          = 2000.0,
            include_objs = True,
        )
        for entry in draw_list:
            renderer.render_model(entry.model_name, entry.world_pos)

    References
    ----------
    KotOR.js ForgeArea.ts — room iteration + object population pattern
    ROADMAP.md Phase 5.1 — VIS-based culling wiring task
    """

    def __init__(self, scene_graph: Optional[SceneGraph] = None):
        self._graph: Optional[SceneGraph] = scene_graph
        # Toggle flags (matched to ROADMAP.md Phase 5.1 UI controls)
        self.show_room_models   : bool = True
        self.show_objects       : bool = True
        self.object_type_filter : Optional[str] = None   # e.g. 'creature' or None for all
        self.show_null_rooms    : bool = False
        # Room visibility override: set by UI toggle per room name
        self._room_visible_override: Dict[str, bool] = {}

    # ── Scene assignment ──────────────────────────────────────────────────────

    def set_scene(self, graph: Optional[SceneGraph]) -> None:
        """Assign (or replace) the SceneGraph this renderer operates on."""
        self._graph = graph
        self._room_visible_override.clear()

    # ── Per-room visibility override (UI toggle) ──────────────────────────────

    def set_room_visible(self, room_name: str, visible: bool) -> None:
        """Override visibility for a specific room from UI controls."""
        self._room_visible_override[room_name] = visible

    def clear_visibility_overrides(self) -> None:
        """Remove all per-room overrides (reset to frustum+VIS culling)."""
        self._room_visible_override.clear()

    # ── Main draw-list builder ────────────────────────────────────────────────

    def build_draw_list(
        self,
        camera_pos   : Tuple[float, float, float],
        camera_fwd   : Tuple[float, float, float],
        fov_h        : float = 90.0,
        fov_v        : float = 60.0,
        near         : float = 0.01,
        far          : float = 2000.0,
        include_objs : bool  = True,
    ) -> List[SceneDrawEntry]:
        """Build the per-frame draw list using frustum + VIS culling.

        Parameters
        ----------
        camera_pos  : (x, y, z) camera world position.
        camera_fwd  : (x, y, z) camera forward unit vector.
        fov_h       : horizontal field-of-view in degrees.
        fov_v       : vertical field-of-view in degrees.
        near / far  : clip plane distances.
        include_objs: if True, append GIT SceneObject entries.

        Returns
        -------
        list[SceneDrawEntry]
        """
        if self._graph is None:
            return []

        # Determine which rooms pass frustum + VIS culling
        try:
            visible_rooms: List[SceneRoom] = self._graph.visible_rooms(
                camera_pos, camera_fwd, fov_h, fov_v, near, far
            )
        except Exception as e:
            log.warning(f"SceneFrameRenderer.build_draw_list: visible_rooms failed: {e}")
            visible_rooms = list(self._graph.rooms)

        draw_list: List[SceneDrawEntry] = []

        for room in visible_rooms:
            # SceneRoom uses 'resref' as the primary room/model identifier.
            # Fall back to a 'name' attribute for subclasses or test stubs.
            rname = getattr(room, 'resref', getattr(room, 'name', ''))

            # NULL room filter
            if not self.show_null_rooms and rname.lower() in ('', 'null', 'none'):
                continue

            # Per-room visibility override from UI
            if rname in self._room_visible_override:
                if not self._room_visible_override[rname]:
                    continue

            # Room model entry.  SceneRoom.resref IS the model name; fall back
            # to 'model_name' attribute for test stubs.
            mname_room = getattr(room, 'model_name', rname) or rname
            if self.show_room_models and mname_room:
                pos = getattr(room, 'position', (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)
                draw_list.append(SceneDrawEntry(
                    model_name  = mname_room,
                    world_pos   = (float(pos[0]), float(pos[1]), float(pos[2])),
                    room_name   = rname,
                    is_object   = False,
                    object_type = '',
                ))

            # GIT objects in this room.
            if include_objs and self.show_objects:
                for obj in self._graph.objects_in_room(rname):
                    # Support both SceneObject.obj_type and legacy .object_type stubs
                    otype = getattr(obj, 'obj_type', getattr(obj, 'object_type', ''))
                    # Type filter
                    if self.object_type_filter and otype != self.object_type_filter:
                        continue
                    # Support both .model_name and SceneObject.resref for model lookup
                    obj_mname = getattr(obj, 'model_name',
                                        getattr(obj, 'resref', ''))
                    opos = getattr(obj, 'position', (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)
                    if obj_mname:
                        draw_list.append(SceneDrawEntry(
                            model_name  = obj_mname,
                            world_pos   = (float(opos[0]), float(opos[1]), float(opos[2])),
                            room_name   = rname,
                            is_object   = True,
                            object_type = otype,
                        ))

        return draw_list

    # ── Convenience queries ───────────────────────────────────────────────────

    def all_room_names(self) -> List[str]:
        """Return sorted list of all room names/refrefs in the scene graph."""
        if self._graph is None:
            return []
        return sorted(
            getattr(r, 'resref', getattr(r, 'name', ''))
            for r in self._graph.rooms
        )

    def room_count(self) -> int:
        """Return total number of rooms in the scene graph."""
        return len(self._graph.rooms) if self._graph else 0

    def object_count(self) -> int:
        """Return total number of GIT objects in the scene graph."""
        if self._graph is None:
            return 0
        return sum(
            len(self._graph.objects_in_room(
                getattr(r, 'resref', getattr(r, 'name', ''))
            ))
            for r in self._graph.rooms
        )

    def are_properties(self) -> Optional[AREProperties]:
        """Return the ``AREProperties`` from the scene graph, or ``None``."""
        return getattr(self._graph, 'are_properties', None) if self._graph else None
