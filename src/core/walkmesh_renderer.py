"""
GhostRigger Walkmesh Renderer — Phase 9.1/9.2
===============================================
Provides data structures and draw-list generation for rendering KotOR
walkmesh (BWM/WOK/PWK/DWK) overlays in the viewport.

Phase 9.1 — WOK data loading (wraps module_format.WOKData)
Phase 9.2 — Walkmesh overlay: colored semi-transparent face polygons
             colored by SurfaceMaterial, matching OdysseyWalkMesh.ts.

Key references:
  • KotOR.js OdysseyWalkMesh.ts (1,020 lines) — face coloring, GL VAO
  • PyKotor/resource/formats/bwm/bwm_data.py — SurfaceMaterial enum
  • PyKotor/gl/models/boundary.py — walkmesh GL VAO setup
  • GhostRigger module_format.py WOKData — existing parser (used as base)
  • Roadmap Phase 9.1-9.4

Surface material color table matches OdysseyWalkMesh.ts RGBA definitions.
All colors are (R, G, B, A) with components in [0.0, 1.0].

Usage:
    loader = WalkmeshLoader()
    wok = loader.from_wok_data(existing_wok_data)
    overlay = WalkmeshOverlay(wok)
    triangles = overlay.colored_triangles()   # for software renderer
    # Each entry: (v0, v1, v2, color_rgba)
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Surface material constants & colors
#  Ref: KotOR.js OdysseyWalkMesh.ts — walkSurfaceColors (RGBA)
#  Ref: PyKotor bwm_data.py SurfaceMaterial enum
# ─────────────────────────────────────────────────────────────────────────────

# Surface material IDs (from PyKotor bwm_data.SurfaceMaterial + KotOR.js)
SURFACE_INVALID      = 0
SURFACE_DIRT         = 1
SURFACE_OBSCURING    = 2
SURFACE_GRASS        = 3
SURFACE_STONE        = 4
SURFACE_WOOD         = 5
SURFACE_WATER        = 6
SURFACE_NON_WALK     = 7    # Wall/blocker (camera + movement blocked)
SURFACE_TRANSPARENT  = 8
SURFACE_CARPET       = 9
SURFACE_METAL        = 10
SURFACE_PUDDLES      = 11
SURFACE_SWAMP        = 12
SURFACE_MUD          = 13
SURFACE_LEAVES       = 14
SURFACE_LAVA         = 15
SURFACE_BOTTOMLESS   = 16
SURFACE_DEEP_WATER   = 17
SURFACE_DOOR         = 18   # walkable door surface
SURFACE_NON_WALK_GRASS = 19
SURFACE_SNOW         = 20   # KotOR 2 extra materials
SURFACE_SAND         = 21
SURFACE_BAREBONES    = 22

# Set of walkable surface IDs (characters can traverse these)
# Ref: module_format.py WALKABLE_IDS
WALKABLE_SURFACES = frozenset({
    SURFACE_DIRT, SURFACE_GRASS, SURFACE_STONE, SURFACE_WOOD,
    SURFACE_CARPET, SURFACE_METAL, SURFACE_PUDDLES, SURFACE_SWAMP,
    SURFACE_MUD, SURFACE_LEAVES, SURFACE_SNOW, SURFACE_SAND,
    SURFACE_BAREBONES, SURFACE_DOOR,
})

NON_WALKABLE_SURFACES = frozenset({
    SURFACE_NON_WALK, SURFACE_BOTTOMLESS, SURFACE_NON_WALK_GRASS,
})

# ── Color table (RGBA floats 0-1) ────────────────────────────────────────────
# Sourced from KotOR.js OdysseyWalkMesh.ts walkSurfaceColors array
# and PyKotor boundary.py material colours.
# Alpha 0.55 for walkable, 0.75 for blockers (makes blockers more prominent).

SURFACE_COLORS: Dict[int, Tuple[float,float,float,float]] = {
    SURFACE_INVALID:      (0.5,  0.5,  0.5,  0.30),  # grey
    SURFACE_DIRT:         (0.60, 0.40, 0.20, 0.55),  # brown
    SURFACE_OBSCURING:    (0.30, 0.30, 0.30, 0.55),  # dark grey
    SURFACE_GRASS:        (0.20, 0.70, 0.20, 0.55),  # green
    SURFACE_STONE:        (0.50, 0.50, 0.50, 0.55),  # grey
    SURFACE_WOOD:         (0.50, 0.30, 0.10, 0.55),  # tan/brown
    SURFACE_WATER:        (0.20, 0.45, 0.80, 0.55),  # blue
    SURFACE_NON_WALK:     (0.80, 0.10, 0.10, 0.75),  # RED — most prominent
    SURFACE_TRANSPARENT:  (0.90, 0.90, 0.90, 0.15),  # near-invisible
    SURFACE_CARPET:       (0.70, 0.30, 0.70, 0.55),  # purple
    SURFACE_METAL:        (0.65, 0.65, 0.75, 0.55),  # silver
    SURFACE_PUDDLES:      (0.30, 0.50, 0.70, 0.55),  # pale blue
    SURFACE_SWAMP:        (0.30, 0.50, 0.10, 0.55),  # dark green
    SURFACE_MUD:          (0.45, 0.30, 0.10, 0.55),  # brown-dark
    SURFACE_LEAVES:       (0.20, 0.60, 0.20, 0.55),  # green-light
    SURFACE_LAVA:         (0.90, 0.30, 0.05, 0.80),  # orange-red
    SURFACE_BOTTOMLESS:   (0.00, 0.00, 0.00, 0.85),  # black
    SURFACE_DEEP_WATER:   (0.10, 0.20, 0.60, 0.80),  # deep blue
    SURFACE_DOOR:         (0.80, 0.80, 0.20, 0.55),  # yellow
    SURFACE_NON_WALK_GRASS: (0.60, 0.20, 0.20, 0.75),  # dark red
    SURFACE_SNOW:         (0.85, 0.90, 0.95, 0.55),  # white-blue
    SURFACE_SAND:         (0.85, 0.75, 0.45, 0.55),  # sandy yellow
    SURFACE_BAREBONES:    (0.55, 0.45, 0.35, 0.55),  # neutral brown
}

_DEFAULT_COLOR = (0.60, 0.60, 0.60, 0.45)  # fallback for unknown material IDs


def surface_color(material_id: int) -> Tuple[float,float,float,float]:
    """Return (R,G,B,A) color for a given surface material ID."""
    return SURFACE_COLORS.get(material_id, _DEFAULT_COLOR)


def surface_name(material_id: int) -> str:
    """Human-readable name for surface material ID."""
    _NAMES = {
        0:  'INVALID',     1:  'DIRT',       2:  'OBSCURING',
        3:  'GRASS',       4:  'STONE',       5:  'WOOD',
        6:  'WATER',       7:  'NON_WALK',    8:  'TRANSPARENT',
        9:  'CARPET',      10: 'METAL',       11: 'PUDDLES',
        12: 'SWAMP',       13: 'MUD',         14: 'LEAVES',
        15: 'LAVA',        16: 'BOTTOMLESS',  17: 'DEEP_WATER',
        18: 'DOOR',        19: 'NON_WALK_GRASS', 20: 'SNOW',
        21: 'SAND',        22: 'BAREBONES',
    }
    return _NAMES.get(material_id, f'SURFACE_{material_id}')


# ─────────────────────────────────────────────────────────────────────────────
#  WalkmeshFace — colored face for rendering
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WalkmeshFace:
    """A single walkmesh triangle with its world-space vertices and color."""
    v0:       Tuple[float,float,float]
    v1:       Tuple[float,float,float]
    v2:       Tuple[float,float,float]
    surface:  int = 0
    walkable: bool = True

    @property
    def color(self) -> Tuple[float,float,float,float]:
        return surface_color(self.surface)

    @property
    def normal(self) -> Tuple[float,float,float]:
        """Compute face normal (for backface culling / shading)."""
        ax = self.v1[0]-self.v0[0]; ay = self.v1[1]-self.v0[1]; az = self.v1[2]-self.v0[2]
        bx = self.v2[0]-self.v0[0]; by = self.v2[1]-self.v0[1]; bz = self.v2[2]-self.v0[2]
        nx = ay*bz - az*by
        ny = az*bx - ax*bz
        nz = ax*by - ay*bx
        l = math.sqrt(nx*nx + ny*ny + nz*nz)
        if l < 1e-9:
            return (0.0, 0.0, 1.0)
        return (nx/l, ny/l, nz/l)


# ─────────────────────────────────────────────────────────────────────────────
#  WalkmeshOverlay — colored triangle list for viewport rendering
# ─────────────────────────────────────────────────────────────────────────────

class WalkmeshOverlay:
    """
    Phase 9.2: Colored walkmesh overlay for the GhostRigger viewport.

    Takes a WOKData (module_format.py) and produces a flat list of
    WalkmeshFace objects, each with world-space vertex positions and
    surface-material RGBA color.

    The viewport can draw these as semi-transparent filled triangles.
    A `W` key toggle controls visibility (Phase 9.4 roadmap item).

    Ref: KotOR.js OdysseyWalkMesh.ts buildMesh() — builds geometry by
         face material group; GhostRigger Roadmap Phase 9.2 color table.
    """

    def __init__(self, world_offset: Tuple = (0.0, 0.0, 0.0)):
        self.faces:  List[WalkmeshFace] = []
        self.offset: Tuple = world_offset      # LYT room position
        self.visible: bool = True               # keyboard W toggle (Phase 9.4)
        self._dirty:  bool = True

    # ── Loading ──────────────────────────────────────────────────────────────

    def load_from_wok(self, wok_data, world_offset: Optional[Tuple] = None):
        """
        Populate faces from a WOKData object (module_format.WOKData).

        wok_data: WOKData with .verts and .faces populated.
        world_offset: (x,y,z) LYT room position — added to all vertices.
        """
        if world_offset is not None:
            self.offset = world_offset

        self.faces.clear()
        ox, oy, oz = self.offset

        verts = getattr(wok_data, 'verts', [])
        wok_faces = getattr(wok_data, 'faces', [])

        n_verts = len(verts)

        for wf in wok_faces:
            v1i, v2i, v3i = wf.v1, wf.v2, wf.v3
            if v1i >= n_verts or v2i >= n_verts or v3i >= n_verts:
                continue

            v0 = (verts[v1i][0]+ox, verts[v1i][1]+oy, verts[v1i][2]+oz)
            v1 = (verts[v2i][0]+ox, verts[v2i][1]+oy, verts[v2i][2]+oz)
            v2 = (verts[v3i][0]+ox, verts[v3i][1]+oy, verts[v3i][2]+oz)

            surf = wf.surface
            walkable = surf in WALKABLE_SURFACES

            self.faces.append(WalkmeshFace(
                v0=v0, v1=v1, v2=v2,
                surface=surf,
                walkable=walkable,
            ))

        self._dirty = False
        log.debug(f"WalkmeshOverlay: loaded {len(self.faces)} faces "
                  f"({sum(1 for f in self.faces if f.walkable)} walkable)")

    def load_from_ascii_wok(self, text: str, world_offset: Optional[Tuple] = None):
        """
        Load from GhostRigger ASCII walkmesh format (written by
        WalkmeshWallGenerator.write_ascii_wok).

        Format:
            verts N
              x y z
            faces M
              v1 v2 v3 surface
        """
        if world_offset is not None:
            self.offset = world_offset

        self.faces.clear()
        verts: List[Tuple] = []
        state = None
        n_expected = 0
        ox, oy, oz = self.offset

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            tokens = line.split()
            if tokens[0] == 'verts':
                state = 'verts'
                n_expected = int(tokens[1]) if len(tokens) > 1 else 0
                continue
            if tokens[0] == 'faces':
                state = 'faces'
                n_expected = int(tokens[1]) if len(tokens) > 1 else 0
                continue
            if state == 'verts':
                if len(tokens) >= 3:
                    verts.append((float(tokens[0])+ox,
                                  float(tokens[1])+oy,
                                  float(tokens[2])+oz))
            elif state == 'faces':
                if len(tokens) >= 4:
                    v1i, v2i, v3i, surf = int(tokens[0]), int(tokens[1]), int(tokens[2]), int(tokens[3])
                    n = len(verts)
                    if v1i < n and v2i < n and v3i < n:
                        self.faces.append(WalkmeshFace(
                            v0=verts[v1i], v1=verts[v2i], v2=verts[v3i],
                            surface=surf,
                            walkable=surf in WALKABLE_SURFACES,
                        ))

        self._dirty = False
        log.debug(f"WalkmeshOverlay: loaded {len(self.faces)} faces from ASCII")

    # ── Filtering & queries ──────────────────────────────────────────────────

    def walkable_faces(self) -> List[WalkmeshFace]:
        return [f for f in self.faces if f.walkable]

    def non_walkable_faces(self) -> List[WalkmeshFace]:
        return [f for f in self.faces if not f.walkable]

    def faces_by_material(self, material_id: int) -> List[WalkmeshFace]:
        return [f for f in self.faces if f.surface == material_id]

    def faces_for_render(self, show_walkable: bool = True,
                         show_non_walkable: bool = True) -> List[WalkmeshFace]:
        """
        Return faces for rendering based on display toggles.
        Ref: Roadmap Phase 9.4 — 'W' key to toggle walkmesh overlay.
        """
        if not self.visible:
            return []
        if show_walkable and show_non_walkable:
            return self.faces
        if show_walkable:
            return self.walkable_faces()
        if show_non_walkable:
            return self.non_walkable_faces()
        return []

    def aabb(self) -> Optional[Tuple[Tuple, Tuple]]:
        """Return (bb_min, bb_max) of all face vertices, or None if empty."""
        if not self.faces:
            return None
        inf = float('inf')
        minx = miny = minz =  inf
        maxx = maxy = maxz = -inf
        for f in self.faces:
            for v in (f.v0, f.v1, f.v2):
                if v[0] < minx: minx = v[0]
                if v[1] < miny: miny = v[1]
                if v[2] < minz: minz = v[2]
                if v[0] > maxx: maxx = v[0]
                if v[1] > maxy: maxy = v[1]
                if v[2] > maxz: maxz = v[2]
        return ((minx, miny, minz), (maxx, maxy, maxz))

    def summary(self) -> str:
        total = len(self.faces)
        walk  = sum(1 for f in self.faces if f.walkable)
        mats  = set(f.surface for f in self.faces)
        return (f"WalkmeshOverlay: {total} faces ({walk} walkable, "
                f"{total-walk} blocked), {len(mats)} materials")

    # ── Boundary edge generator (Phase 9 — walkmesh write helper) ────────────

    def boundary_edges(self) -> List[Tuple[Tuple,Tuple]]:
        """
        Return boundary edges: pairs of (v_a, v_b) where one side is
        walkable and the other is non-walkable or missing.
        Used for walkmesh perimeter visualization and Phase 9.3 wall generation.
        Ref: PyKotor bwm_data.BWM.perimeter_edges().
        """
        # Build edge → face-side mapping
        # Key: canonical edge (min_v, max_v); value: list of (face_idx, is_walkable)
        edge_map: Dict = {}

        for fi, face in enumerate(self.faces):
            verts = [face.v0, face.v1, face.v2]
            for ei in range(3):
                va = verts[ei]
                vb = verts[(ei+1) % 3]
                # Canonical key: sort by tuple comparison
                key = (min(va, vb), max(va, vb))
                edge_map.setdefault(key, [])
                edge_map[key].append((fi, face.walkable))

        edges = []
        for (va, vb), sides in edge_map.items():
            # Boundary: only one face uses this edge (exterior)
            # OR two faces with mixed walkability
            if len(sides) == 1:
                _, is_walk = sides[0]
                if is_walk:
                    edges.append((va, vb))
            elif len(sides) == 2:
                w0, w1 = sides[0][1], sides[1][1]
                if w0 != w1:
                    edges.append((va, vb))
        return edges


# ─────────────────────────────────────────────────────────────────────────────
#  WalkmeshLoader — convenience methods
# ─────────────────────────────────────────────────────────────────────────────

class WalkmeshLoader:
    """
    Phase 9.1: Load walkmesh data from various sources.

    Wraps module_format.WOKData and provides WalkmeshOverlay creation.

    Methods:
      from_wok_data(wok, offset)  → WalkmeshOverlay
      from_file(path, offset)     → WalkmeshOverlay
      from_scene_room(room)       → WalkmeshOverlay  (if room.wok is set)

    Ref: kotorblender — WOK co-import with MDL (when loading room model,
         also load <resref>.wok);  Roadmap Phase 9.1.
    """

    def from_wok_data(self, wok_data,
                      world_offset: Tuple = (0.0, 0.0, 0.0)) -> WalkmeshOverlay:
        """Create a WalkmeshOverlay from an existing WOKData object."""
        overlay = WalkmeshOverlay(world_offset)
        overlay.load_from_wok(wok_data, world_offset)
        return overlay

    def from_file(self, path: str,
                  world_offset: Tuple = (0.0, 0.0, 0.0)) -> Optional[WalkmeshOverlay]:
        """
        Load WOK from a binary file path.
        Requires module_format.WOKData.from_file() to be available.
        """
        try:
            from .module_format import WOKData
            wok = WOKData.from_file(path)
            return self.from_wok_data(wok, world_offset)
        except Exception as e:
            log.warning(f"WalkmeshLoader.from_file({path}): {e}")
            return None

    def from_scene_room(self, room) -> Optional[WalkmeshOverlay]:
        """
        Create a WalkmeshOverlay from a SceneRoom that has room.wok set.
        Returns None if room.wok is None.
        """
        wok = getattr(room, 'wok', None)
        if wok is None:
            return None
        return self.from_wok_data(wok, room.position)

    def load_all_room_overlays(self, scene) -> Dict[str, WalkmeshOverlay]:
        """
        Create WalkmeshOverlay for every room in the scene that has a WOK.
        Returns dict of resref → WalkmeshOverlay.
        Ref: kotorblender WOK co-import pattern.
        """
        overlays = {}
        for room in getattr(scene, 'rooms', []):
            overlay = self.from_scene_room(room)
            if overlay is not None:
                overlays[room.resref] = overlay
                log.debug(f"WalkmeshLoader: loaded overlay for room '{room.resref}': "
                          f"{overlay.summary()}")
        log.info(f"WalkmeshLoader: {len(overlays)}/{len(scene.rooms)} "
                 f"room walkmeshes loaded")
        return overlays


# ─────────────────────────────────────────────────────────────────────────────
#  DrawList — flattened renderable for software renderer
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WalkmeshDrawEntry:
    """One renderable walkmesh triangle with world-space verts and RGBA color."""
    v0:    Tuple[float,float,float]
    v1:    Tuple[float,float,float]
    v2:    Tuple[float,float,float]
    color: Tuple[float,float,float,float]   # pre-fetched RGBA


def build_draw_list(overlays: Dict[str, WalkmeshOverlay],
                    show_walkable: bool = True,
                    show_non_walkable: bool = True) -> List[WalkmeshDrawEntry]:
    """
    Flatten all WalkmeshOverlay objects into a single draw list for the
    software renderer (viewport.py FrameRenderer).

    The software renderer iterates this list and draws each entry as a
    filled, alpha-blended triangle using Pillow ImageDraw.polygon().

    Ref: Roadmap Phase 9.2; viewport.py FrameRenderer._draw_walkmesh_overlay().
    """
    entries: List[WalkmeshDrawEntry] = []
    for overlay in overlays.values():
        if not overlay.visible:
            continue
        for face in overlay.faces_for_render(show_walkable, show_non_walkable):
            entries.append(WalkmeshDrawEntry(
                v0    = face.v0,
                v1    = face.v1,
                v2    = face.v2,
                color = face.color,
            ))
    return entries
