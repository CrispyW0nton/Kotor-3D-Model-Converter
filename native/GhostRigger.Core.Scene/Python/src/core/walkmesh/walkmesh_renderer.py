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
SURFACE_MATERIAL_20  = 20   # reserved/non-walk in Odyssey
SURFACE_MATERIAL_21  = 21
SURFACE_MATERIAL_22  = 22
SURFACE_MATERIAL_23  = 23
SURFACE_MATERIAL_24  = 24
SURFACE_MATERIAL_25  = 25
SURFACE_MATERIAL_26  = 26
SURFACE_MATERIAL_27  = 27
SURFACE_MATERIAL_28  = 28
SURFACE_MATERIAL_29  = 29
SURFACE_TRIGGER      = 30

# Set of walkable surface IDs (characters can traverse these)
# Ref: module_format.py WALKABLE_IDS
WALKABLE_SURFACES = frozenset({
    SURFACE_DIRT, SURFACE_GRASS, SURFACE_STONE, SURFACE_WOOD,
    SURFACE_WATER, SURFACE_CARPET, SURFACE_METAL, SURFACE_PUDDLES,
    SURFACE_SWAMP, SURFACE_MUD, SURFACE_LEAVES, SURFACE_DOOR,
    SURFACE_TRIGGER,
})

NON_WALKABLE_SURFACES = frozenset(set(range(31)) - set(WALKABLE_SURFACES))

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
    SURFACE_TRIGGER:      (0.95, 0.55, 0.10, 0.55),  # orange
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
        18: 'DOOR',        19: 'NON_WALK_GRASS', 20: 'SURFACE_MATERIAL_20',
        21: 'SURFACE_MATERIAL_21', 22: 'SURFACE_MATERIAL_22',
        23: 'SURFACE_MATERIAL_23', 24: 'SURFACE_MATERIAL_24',
        25: 'SURFACE_MATERIAL_25', 26: 'SURFACE_MATERIAL_26',
        27: 'SURFACE_MATERIAL_27', 28: 'SURFACE_MATERIAL_28',
        29: 'SURFACE_MATERIAL_29', 30: 'TRIGGER',
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
            from ..modules.module_format import WOKData
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


# ─────────────────────────────────────────────────────────────────────────────
#  WalkmeshWriter — Phase 9.3
# ─────────────────────────────────────────────────────────────────────────────

class WalkmeshWriter:
    """
    Serialise a ``WalkmeshOverlay`` (or a raw ``WOKData``) back to a valid
    Aurora BWM binary blob and optionally write it to disk.

    Phase 9.3 — Walkmesh Write.

    The Aurora BWM format (also used for PWK door walkmeshes and DWK placeable
    walkmeshes) is straightforward:

    Header (136 bytes):
      0x00  sig          "BWM "  (4 bytes)
      0x04  ver          "V1.0"  (4 bytes)
      0x08  wok_type     uint32  (1 = room BWM)
      0x0C  reserved     [52 bytes zero padding]
      0x38  vert_count   uint32
      0x3C  vert_offset  uint32
      0x40  face_count   uint32
      0x44  face_offset  uint32  (3 × uint16 per face)
      0x48  mat_offset   uint32  (1 × uint32 per face — surface material ID)
      0x4C  adj_offset   uint32  (3 × int32  per face — adjacent face indices, -1 = none)
      0x50  [remaining header zeros to offset 0x88]

    Data sections (immediately after header, in declared order):
      verts        → faces → materials → adjacencies

    References:
      PyKotor/resource/formats/bwm/io_bwm.py (writer)
      Kotor.NET/Formats/KotorBWM/KotorBWMBinaryWriter.cs
      KotOR.js OdysseyWalkMesh.ts
      Roadmap Phase 9.3
    """

    # Sentinel for "no adjacent face"
    NO_ADJ = -1

    def to_bytes(self, overlay: 'WalkmeshOverlay') -> bytes:
        """
        Convert a WalkmeshOverlay to a binary BWM blob.

        The overlay's world-space vertex positions are used as-is (the world
        offset was already baked in when the overlay was built from a room).

        Returns raw bytes suitable for writing to a .wok / .dwk / .pwk file.
        """
        verts, faces, materials, adjacencies = self._extract_geometry(overlay)
        return self._pack(verts, faces, materials, adjacencies)

    def to_bytes_from_wok(self, wok_data) -> bytes:
        """
        Re-serialise a raw ``WOKData`` object (from module_format.py).

        Delegates to ``WOKData.to_bytes()`` which has its own implementation.
        This wrapper normalises the API so callers can use WalkmeshWriter for
        both sources.
        """
        return wok_data.to_bytes()

    def write_file(self, overlay: 'WalkmeshOverlay', path: str) -> int:
        """
        Write the overlay to a BWM file at ``path``.

        Returns the number of bytes written.
        """
        from pathlib import Path as _Path
        data = self.to_bytes(overlay)
        _Path(path).write_bytes(data)
        log.info("WalkmeshWriter: wrote %d bytes to %s", len(data), path)
        return len(data)

    def write_wok_file(self, wok_data, path: str) -> int:
        """Write a WOKData object to a BWM file."""
        from pathlib import Path as _Path
        data = wok_data.to_bytes()
        _Path(path).write_bytes(data)
        log.info("WalkmeshWriter: wrote %d bytes (WOKData) to %s", len(data), path)
        return len(data)

    # ── Round-trip helpers ─────────────────────────────────────────────────

    @staticmethod
    def roundtrip(overlay: 'WalkmeshOverlay') -> 'WalkmeshOverlay':
        """
        Serialise ``overlay`` to bytes and re-parse into a new WalkmeshOverlay.

        Used for round-trip fidelity tests (Phase 9.3 test suite).
        """
        writer = WalkmeshWriter()
        data   = writer.to_bytes(overlay)
        try:
            from ..modules.module_format import WOKData
        except ImportError:
            from module_format import WOKData  # type: ignore[no-redef]
        wok_rt = WOKData.from_bytes(data)
        loader = WalkmeshLoader()
        return loader.from_wok_data(wok_rt)

    # ── Internal ──────────────────────────────────────────────────────────

    def _extract_geometry(
        self, overlay: 'WalkmeshOverlay'
    ) -> Tuple[
        List[Tuple[float,float,float]],   # verts
        List[Tuple[int,int,int]],          # face vertex indices
        List[int],                          # material IDs
        List[Tuple[int,int,int]],           # adjacencies
    ]:
        """
        Convert the overlay's WalkmeshFace list into raw geometry arrays
        suitable for binary packing.

        De-duplicates vertices (within float tolerance) to keep the output
        compact.  Adjacency is reconstructed from shared-edge detection.
        """
        import struct as _s

        # Build vertex list (de-duplicate)
        vert_to_idx: Dict[Tuple, int] = {}
        verts: List[Tuple[float,float,float]] = []

        def _add_vert(v: Tuple[float,float,float]) -> int:
            # Round to 5 decimal places to merge near-duplicate vertices
            key = (round(v[0], 5), round(v[1], 5), round(v[2], 5))
            if key not in vert_to_idx:
                vert_to_idx[key] = len(verts)
                verts.append(v)
            return vert_to_idx[key]

        face_triples: List[Tuple[int,int,int]] = []
        materials:    List[int] = []

        for face in overlay.faces:
            i0 = _add_vert(face.v0)
            i1 = _add_vert(face.v1)
            i2 = _add_vert(face.v2)
            face_triples.append((i0, i1, i2))
            materials.append(face.surface)

        # Rebuild adjacency: two faces are adjacent on edge (a,b) if one has
        # edge a→b and the other has edge b→a.
        adjacencies = self._compute_adjacency(face_triples)
        return verts, face_triples, materials, adjacencies

    @staticmethod
    def _compute_adjacency(
        face_triples: List[Tuple[int,int,int]]
    ) -> List[Tuple[int,int,int]]:
        """
        Build the adjacency list for BWM: for each face, three adjacent face
        indices (one per edge), or -1 if the edge is on the boundary.

        An edge is shared between face i (edge k, vertices a→b) and face j
        (edge m, vertices b→a — reversed).

        Ref: Kotor.NET BWM.CalculateAABBs() edge-sharing logic.
        """
        # Build edge → (face_idx, edge_idx) map
        edge_map: Dict[Tuple[int,int], Tuple[int,int]] = {}
        for fi, (v0, v1, v2) in enumerate(face_triples):
            edges = [(v0, v1), (v1, v2), (v2, v0)]
            for ei, (a, b) in enumerate(edges):
                edge_map[(a, b)] = (fi, ei)

        result: List[Tuple[int,int,int]] = []
        for fi, (v0, v1, v2) in enumerate(face_triples):
            edges = [(v0, v1), (v1, v2), (v2, v0)]
            adjs = []
            for (a, b) in edges:
                # Look for the reverse edge in another face
                rev = edge_map.get((b, a))
                if rev is not None and rev[0] != fi:
                    adjs.append(rev[0])
                else:
                    adjs.append(-1)
            result.append((adjs[0], adjs[1], adjs[2]))
        return result

    @staticmethod
    def _pack(
        verts:       List[Tuple[float,float,float]],
        faces:       List[Tuple[int,int,int]],
        materials:   List[int],
        adjacencies: List[Tuple[int,int,int]],
    ) -> bytes:
        """Pack the geometry arrays into a BWM binary blob."""
        import struct as _s

        nv = len(verts)
        nf = len(faces)

        vert_sz = nv * 12          # 3 × float32
        face_sz = nf * 6           # 3 × uint16
        mat_sz  = nf * 4           # 1 × uint32
        adj_sz  = nf * 12          # 3 × int32

        header_size = 136
        vert_off = header_size
        face_off = vert_off + vert_sz
        mat_off  = face_off + face_sz
        adj_off  = mat_off  + mat_sz

        buf = bytearray(adj_off + adj_sz)

        buf[0:4] = b'BWM '
        buf[4:8] = b'V1.0'
        _s.pack_into('<I', buf, 8,  1)          # wok_type = 1 (room)
        _s.pack_into('<I', buf, 56, nv)
        _s.pack_into('<I', buf, 60, vert_off)
        _s.pack_into('<I', buf, 64, nf)
        _s.pack_into('<I', buf, 68, face_off)
        _s.pack_into('<I', buf, 72, mat_off)
        _s.pack_into('<I', buf, 76, adj_off)

        for i, (x, y, z) in enumerate(verts):
            _s.pack_into('<fff', buf, vert_off + i*12, x, y, z)

        for i, (v0, v1, v2) in enumerate(faces):
            _s.pack_into('<HHH', buf, face_off + i*6,  v0, v1, v2)
            _s.pack_into('<I',   buf, mat_off  + i*4,  materials[i])
            a0, a1, a2 = adjacencies[i] if i < len(adjacencies) else (-1, -1, -1)
            _s.pack_into('<iii', buf, adj_off  + i*12, a0, a1, a2)

        return bytes(buf)


# ─────────────────────────────────────────────────────────────────────────────
#  WalkmeshToggleController — Phase 9.4
# ─────────────────────────────────────────────────────────────────────────────

class WalkmeshToggleController:
    """
    Keyboard-driven controller for toggling walkmesh overlay visibility.

    Phase 9.4 — Keyboard Toggle (``W`` key binding).

    The controller holds a reference to a dict of ``WalkmeshOverlay`` objects
    (typically maintained by the viewport FrameRenderer) and provides:

      • ``toggle()``         — flip global visibility
      • ``on_key(key)``      — handle key events (returns True if consumed)
      • ``toggle_room(name)``— flip a single room's overlay visibility
      • ``set_all(visible)`` — bulk show/hide
      • ``visible``          — read global visibility state

    The default key binding is ``'W'`` (case-insensitive), matching the
    Roadmap Phase 9.4 keyboard shortcut table.

    Usage in viewport.py FrameRenderer::

        self._wm_toggle = WalkmeshToggleController(self._wm_overlays)
        # In keyPressEvent:
        consumed = self._wm_toggle.on_key(event.key_name)
    """

    DEFAULT_KEY = 'w'

    def __init__(
        self,
        overlays: Optional[Dict[str, 'WalkmeshOverlay']] = None,
        key: str = DEFAULT_KEY,
    ) -> None:
        self._overlays: Dict[str, 'WalkmeshOverlay'] = overlays or {}
        self._key      = key.lower()
        self._visible  = True   # global toggle state

    @property
    def visible(self) -> bool:
        """Current global visibility state of the walkmesh overlay."""
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        self._visible = value
        self._sync_overlays()

    def toggle(self) -> bool:
        """
        Flip the global walkmesh overlay visibility.

        Returns the new visibility state.
        """
        self._visible = not self._visible
        self._sync_overlays()
        log.debug("WalkmeshToggleController: visibility → %s", self._visible)
        return self._visible

    def on_key(self, key: str) -> bool:
        """
        Handle a key press event.

        Returns True if the event was consumed (key matched), False otherwise.

        ``key`` should be the key character (e.g. ``'w'``, ``'W'``, ``'w'``).
        """
        if key.lower() == self._key:
            self.toggle()
            return True
        return False

    def toggle_room(self, room_name: str) -> Optional[bool]:
        """
        Toggle visibility of a single room's walkmesh overlay.

        Returns the new visibility state, or None if the room is not found.
        """
        overlay = self._overlays.get(room_name)
        if overlay is None:
            return None
        overlay.visible = not overlay.visible
        log.debug("WalkmeshToggleController: room '%s' → %s", room_name, overlay.visible)
        return overlay.visible

    def set_all(self, visible: bool) -> None:
        """Show or hide all walkmesh overlays at once."""
        self._visible = visible
        self._sync_overlays()

    def set_overlays(self, overlays: Dict[str, 'WalkmeshOverlay']) -> None:
        """Replace the managed overlays dict (e.g. after a scene reload)."""
        self._overlays = overlays
        self._sync_overlays()

    def set_key(self, key: str) -> None:
        """Change the toggle key binding."""
        self._key = key.lower()

    @property
    def key(self) -> str:
        """Current toggle key character."""
        return self._key

    @property
    def overlay_count(self) -> int:
        """Number of overlays currently managed."""
        return len(self._overlays)

    # ── Internal ──────────────────────────────────────────────────────────

    def _sync_overlays(self) -> None:
        """Propagate the global visible state to all overlay objects."""
        for overlay in self._overlays.values():
            overlay.visible = self._visible


# ─────────────────────────────────────────────────────────────────────────────
#  v7.2 Walkmesh FBX Material Export (Finding 4.3 — KotorBlender walkmesh.py)
# ─────────────────────────────────────────────────────────────────────────────

# FBX-compatible material definitions for each walkmesh surface type.
# Each material maps a surface ID to an FBX material name and diffuse color
# so that Unreal Engine can assign physics materials per surface type.
# Reference: KotorBlender walkmesh.py + constants.py WALKMESH_MATERIALS;
#            reone bwmreader.h surface type constants.
WALKMESH_FBX_MATERIALS: Dict[int, Dict[str, Any]] = {
    SURFACE_INVALID:        {'name': 'WOK_Invalid',       'diffuse': (0.5, 0.5, 0.5)},
    SURFACE_DIRT:           {'name': 'WOK_Dirt',          'diffuse': (0.60, 0.40, 0.20)},
    SURFACE_OBSCURING:      {'name': 'WOK_Obscuring',    'diffuse': (0.30, 0.30, 0.30)},
    SURFACE_GRASS:          {'name': 'WOK_Grass',         'diffuse': (0.20, 0.70, 0.20)},
    SURFACE_STONE:          {'name': 'WOK_Stone',         'diffuse': (0.50, 0.50, 0.50)},
    SURFACE_WOOD:           {'name': 'WOK_Wood',          'diffuse': (0.50, 0.30, 0.10)},
    SURFACE_WATER:          {'name': 'WOK_Water',         'diffuse': (0.20, 0.45, 0.80)},
    SURFACE_NON_WALK:       {'name': 'WOK_NonWalk',       'diffuse': (0.80, 0.10, 0.10)},
    SURFACE_TRANSPARENT:    {'name': 'WOK_Transparent',   'diffuse': (0.90, 0.90, 0.90)},
    SURFACE_CARPET:         {'name': 'WOK_Carpet',        'diffuse': (0.70, 0.30, 0.70)},
    SURFACE_METAL:          {'name': 'WOK_Metal',         'diffuse': (0.65, 0.65, 0.75)},
    SURFACE_PUDDLES:        {'name': 'WOK_Puddles',       'diffuse': (0.30, 0.50, 0.70)},
    SURFACE_SWAMP:          {'name': 'WOK_Swamp',         'diffuse': (0.30, 0.50, 0.10)},
    SURFACE_MUD:            {'name': 'WOK_Mud',           'diffuse': (0.45, 0.30, 0.10)},
    SURFACE_LEAVES:         {'name': 'WOK_Leaves',        'diffuse': (0.20, 0.60, 0.20)},
    SURFACE_LAVA:           {'name': 'WOK_Lava',          'diffuse': (0.90, 0.30, 0.05)},
    SURFACE_BOTTOMLESS:     {'name': 'WOK_Bottomless',    'diffuse': (0.00, 0.00, 0.00)},
    SURFACE_DEEP_WATER:     {'name': 'WOK_DeepWater',     'diffuse': (0.10, 0.20, 0.60)},
    SURFACE_DOOR:           {'name': 'WOK_Door',          'diffuse': (0.80, 0.80, 0.20)},
    SURFACE_NON_WALK_GRASS: {'name': 'WOK_NonWalkGrass',  'diffuse': (0.60, 0.20, 0.20)},
    SURFACE_TRIGGER:        {'name': 'WOK_Trigger',       'diffuse': (0.95, 0.55, 0.10)},
}


def get_walkmesh_fbx_material(surface_id: int) -> Dict[str, Any]:
    """Return FBX material properties for a walkmesh surface type.

    The returned dict contains 'name' (FBX material name) and 'diffuse'
    (RGB tuple) suitable for writing into FBX material blocks.

    In Unreal Engine, these material names can be mapped to UE5 Physical
    Materials via a data table, enabling automatic footstep sounds and
    surface-dependent gameplay effects.

    Returns
    -------
    dict with 'name' and 'diffuse' keys.
    """
    return WALKMESH_FBX_MATERIALS.get(surface_id, {
        'name': f'WOK_Surface{surface_id}',
        'diffuse': (0.60, 0.60, 0.60),
    })


def walkmesh_to_fbx_materials(overlay: 'WalkmeshOverlay') -> Dict[str, List[int]]:
    """Group walkmesh faces by surface type for FBX multi-material export.

    Returns a dict mapping FBX material name → list of face indices.
    This enables exporting the walkmesh as a single mesh with multiple
    FBX materials (one per surface type), which UE5 imports as a
    multi-material Static Mesh with named material slots.

    Parameters
    ----------
    overlay : WalkmeshOverlay
        A loaded walkmesh overlay with .faces list.

    Returns
    -------
    dict[str, list[int]]
        Material name → face index list.
    """
    mat_faces: Dict[str, List[int]] = {}
    for fi, face in enumerate(overlay.faces):
        mat_info = get_walkmesh_fbx_material(face.surface)
        mat_name = mat_info['name']
        if mat_name not in mat_faces:
            mat_faces[mat_name] = []
        mat_faces[mat_name].append(fi)
    return mat_faces
