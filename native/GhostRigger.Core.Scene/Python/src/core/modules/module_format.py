"""
KotOR Module File Format Readers/Writers
=========================================
Handles all files that make up a KotOR module:
  • LYT  – Layout file  (room positions, doors, emitters, walkmesh hooks)
  • VIS  – Visibility file (which rooms can see each other)
  • ARE  – Area GFF (lighting, fog, skybox, minimap coordinates)
  • GIT  – Game Instance Table GFF (placed creatures, doors, placeables, triggers, waypoints)
  • IFO  – Module Info GFF (entry point, tag, name)
  • WOK  – Walkmesh (binary, face/vertex/surface data)
  • PTH  – Path data

Full pipeline:
  parse → modify → write_back

All reads are done from raw bytes so they work both from game BIFs and from
loose Override files.
"""

import struct
import os
import re
import math
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Any

from ..game.game_library_ext import GFFReader, RES_ARE, RES_IFO, RES_WOK

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  LYT  (Layout file)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LYTRoom:
    model:  str    # resref of the room MDL
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

@dataclass
class LYTDoorHook:
    """Door hook placement from LYT file.

    v7.2 FIX-DOORHOOK (Finding 4.2 — KotorBlender lyt.py cross-ref):
    KotorBlender lyt.py exports door hooks with 7-value format:
        parent_name door_name x y z qx qy qz qw
    The quaternion (qx,qy,qz,qw) specifies the door's orientation.
    GhostRigger previously only parsed position (x,y,z) and ignored rotation.
    Now we store the full quaternion for correct door placement in module export.
    Reference: KotorBlender lyt.py lines 64-108; KotOR.js ForgeArea.ts door loading.
    """
    name:  str
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    # v7.2: Door orientation quaternion (Finding 4.2)
    qx: float = 0.0
    qy: float = 0.0
    qz: float = 0.0
    qw: float = 1.0   # identity rotation by default

@dataclass
class LYTLayout:
    rooms:     List[LYTRoom]    = field(default_factory=list)
    doorhooks: List[LYTDoorHook] = field(default_factory=list)
    others:    List[str]         = field(default_factory=list)   # unparsed lines

    # ── Parser ──────────────────────────────────────────────────────────────

    @classmethod
    def from_text(cls, text: str) -> 'LYTLayout':
        lyt = cls()
        lines = text.splitlines()
        state: Optional[str] = None
        count  = 0
        idx    = 0
        i = 0
        while i < len(lines):
            raw = lines[i].strip()
            i += 1
            if not raw or raw.startswith('#'):
                continue

            tokens = raw.split()
            if not tokens:
                continue
            keyword = tokens[0].lower()

            if keyword in ('roomcount', 'doorhookcount', 'obstaclecount',
                           'articulatedmeshcount', 'othercounttype'):
                try:
                    count = int(tokens[1]) if len(tokens) > 1 else 0
                except ValueError:
                    count = 0
                state = keyword
                idx   = 0
                continue

            if keyword == 'donelayout':
                state = None
                continue

            # Parse room entry: "modelname  x  y  z"
            if state == 'roomcount':
                try:
                    mx, my, mz = float(tokens[1]), float(tokens[2]), float(tokens[3])
                    lyt.rooms.append(LYTRoom(tokens[0].lower(), mx, my, mz))
                except (IndexError, ValueError):
                    pass
                idx += 1
                if idx >= count:
                    state = None
                continue

            # Parse doorhook entry
            # v7.2 FIX-DOORHOOK (Finding 4.2): Parse optional quaternion (qx,qy,qz,qw)
            # KotorBlender format: parent_name door_name x y z qx qy qz qw
            # Minimal format: name x y z
            if state == 'doorhookcount':
                try:
                    dx, dy, dz = float(tokens[1]), float(tokens[2]), float(tokens[3])
                    # Parse optional quaternion rotation (tokens 4-7)
                    qx = float(tokens[4]) if len(tokens) > 4 else 0.0
                    qy = float(tokens[5]) if len(tokens) > 5 else 0.0
                    qz = float(tokens[6]) if len(tokens) > 6 else 0.0
                    qw = float(tokens[7]) if len(tokens) > 7 else 1.0
                    lyt.doorhooks.append(LYTDoorHook(
                        tokens[0].lower(), dx, dy, dz, qx, qy, qz, qw))
                except (IndexError, ValueError):
                    pass
                idx += 1
                if idx >= count:
                    state = None
                continue

            lyt.others.append(raw)
        return lyt

    @classmethod
    def from_file(cls, path: str) -> 'LYTLayout':
        return cls.from_text(Path(path).read_text(encoding='latin-1', errors='replace'))

    # ── Writer ──────────────────────────────────────────────────────────────

    def to_text(self) -> str:
        lines = []
        dependency = "layout.max"
        if self.rooms:
            first_room = self.rooms[0].model
            dependency = f"{first_room.split('_', 1)[0]}.max"
        lines.append("#MAXLAYOUT ASCII")
        lines.append(f"filedependancy {dependency}")
        lines.append("beginlayout")
        lines.append(f"roomcount {len(self.rooms)}")
        for r in self.rooms:
            lines.append(f"  {r.model}  {r.x:.6f}  {r.y:.6f}  {r.z:.6f}")
        lines.append("trackcount 0")
        lines.append("obstaclecount 0")
        if self.doorhooks:
            lines.append(f"doorhookcount {len(self.doorhooks)}")
            for d in self.doorhooks:
                # v7.2: Write quaternion if non-identity (Finding 4.2)
                if abs(d.qx) > 1e-6 or abs(d.qy) > 1e-6 or abs(d.qz) > 1e-6 or abs(d.qw - 1.0) > 1e-6:
                    lines.append(f"  {d.name}  {d.x:.6f}  {d.y:.6f}  {d.z:.6f}  "
                                 f"{d.qx:.6f}  {d.qy:.6f}  {d.qz:.6f}  {d.qw:.6f}")
                else:
                    lines.append(f"  {d.name}  {d.x:.6f}  {d.y:.6f}  {d.z:.6f}")
        else:
            lines.append("doorhookcount 0")
        lines.append("donelayout")
        return "\n".join(lines) + "\n"

    def write(self, path: str):
        Path(path).write_text(self.to_text(), encoding='latin-1')


# ─────────────────────────────────────────────────────────────────────────────
#  VIS  (Visibility file)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class VISData:
    """Maps each room name → set of visible room names."""
    visibility: Dict[str, List[str]] = field(default_factory=dict)

    @classmethod
    def from_text(cls, text: str) -> 'VISData':
        vis = cls()
        current_room: Optional[str] = None
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            tokens = line.split()
            # Stock VIS room headers are "room count"; older GhostRigger files
            # used just "room".  Support both, but always write the stock form.
            if not raw_line[0].isspace() and tokens:
                current_room = tokens[0].lower()
                vis.visibility.setdefault(current_room, [])
            elif current_room and tokens:
                vis.visibility[current_room].append(tokens[0].lower())
        return vis

    @classmethod
    def from_file(cls, path: str) -> 'VISData':
        return cls.from_text(Path(path).read_text(encoding='latin-1', errors='replace'))

    def to_text(self) -> str:
        lines = []
        for room, visible in sorted(self.visibility.items()):
            lines.append(f"{room} {len(visible)}")
            for v in visible:
                lines.append(f"  {v}")
        return "\n".join(lines) + "\n"

    def write(self, path: str):
        Path(path).write_text(self.to_text(), encoding='latin-1')

    def add_full_visibility(self, rooms: List[str]):
        """Make all rooms visible from each other (useful for small custom modules)."""
        for r in rooms:
            self.visibility[r.lower()] = [x.lower() for x in rooms]


# ─────────────────────────────────────────────────────────────────────────────
#  ARE  (Area GFF — lighting, fog, skybox, minimap)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AREData:
    """Parsed fields from the .are GFF that modders commonly edit."""
    # Lighting
    sun_ambient:    Tuple[int,int,int]  = (64, 64, 64)
    sun_diffuse:    Tuple[int,int,int]  = (255, 255, 255)
    sun_fog:        int                 = 0
    fog_color:      Tuple[int,int,int]  = (0, 0, 0)
    fog_near:       float               = 100.0
    fog_far:        float               = 200.0
    # Minimap
    map_pt1_x: float = 0.0
    map_pt1_y: float = 0.0
    map_pt2_x: float = 1.0
    map_pt2_y: float = 1.0
    world_pt1_x: float = 0.0
    world_pt1_y: float = 0.0
    world_pt2_x: float = 100.0
    world_pt2_y: float = 100.0
    # Name
    name:     str = ""
    tag:      str = ""
    # raw parsed dict (full GFF tree)
    _raw: Optional[Dict] = field(default=None, repr=False)

    @classmethod
    def from_bytes(cls, data: bytes) -> 'AREData':
        raw = GFFReader.from_bytes(data)
        if raw is None:
            return cls()
        a = cls(_raw=raw)
        def _get(key, default=None):
            v = raw.get(key)
            return v if v is not None else default

        # Ambient/diffuse colors are stored as packed DWORD RGB
        def _unpack_color(v, default=(0,0,0)):
            if not isinstance(v, int):
                return default
            r = (v >> 16) & 0xFF
            g = (v >> 8)  & 0xFF
            b =  v        & 0xFF
            return (r, g, b)

        a.sun_ambient = _unpack_color(_get('SunAmbientColor', 0x404040), (64,64,64))
        a.sun_diffuse = _unpack_color(_get('SunDiffuseColor', 0xFFFFFF), (255,255,255))
        a.sun_fog     = int(_get('SunFog', 0))
        a.fog_color   = _unpack_color(_get('FogColor', 0), (0,0,0))
        a.fog_near    = float(_get('FogNearDist',  100.0))
        a.fog_far     = float(_get('FogFarDist',   200.0))
        a.map_pt1_x   = float(_get('MapPt1X', 0.0))
        a.map_pt1_y   = float(_get('MapPt1Y', 0.0))
        a.map_pt2_x   = float(_get('MapPt2X', 1.0))
        a.map_pt2_y   = float(_get('MapPt2Y', 1.0))
        a.world_pt1_x = float(_get('WorldPt1X', 0.0))
        a.world_pt1_y = float(_get('WorldPt1Y', 0.0))
        a.world_pt2_x = float(_get('WorldPt2X', 100.0))
        a.world_pt2_y = float(_get('WorldPt2Y', 100.0))
        # Name / tag
        n = _get('Name', {})
        if isinstance(n, dict):
            a.name = n.get('strings', {}).get(0, '') or ''
        elif isinstance(n, str):
            a.name = n
        a.tag = str(_get('Tag', ''))
        return a


# ─────────────────────────────────────────────────────────────────────────────
#  GIT  (Game Instance Table GFF)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class GITCreature:
    resref: str
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    bearing: float = 0.0

@dataclass
class GITDoor:
    resref:  str
    tag:     str   = ""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    bearing: float = 0.0
    linked_to: str = ""
    linked_to_module: str = ""
    transition: int = 0

@dataclass
class GITPlaceable:
    resref: str
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    bearing: float = 0.0

@dataclass
class GITWaypoint:
    resref: str
    tag:    str   = ""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    bearing: float = 0.0

@dataclass
class GITTrigger:
    resref: str
    tag:    str = ""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    geometry: List[Tuple[float,float,float]] = field(default_factory=list)
    linked_to: str = ""
    transition: int = 0

@dataclass
class GITEncounter:
    resref: str
    tag:    str = ""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

@dataclass
class GITSound:
    resref: str
    tag:    str = ""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

@dataclass
class GITStore:
    resref: str
    tag:    str = ""

@dataclass
class GITCamera:
    camera_id: int = 0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    orientation: Tuple[float,float,float,float] = (0.0, 0.0, 0.0, 1.0)
    field_of_view: float = 45.0
    height: float = 0.0
    mic_range: float = 0.0
    pitch: float = 0.0

@dataclass
class GITData:
    cameras:    List[GITCamera]    = field(default_factory=list)
    creatures:  List[GITCreature]  = field(default_factory=list)
    doors:      List[GITDoor]      = field(default_factory=list)
    placeables: List[GITPlaceable] = field(default_factory=list)
    waypoints:  List[GITWaypoint]  = field(default_factory=list)
    triggers:   List[GITTrigger]   = field(default_factory=list)
    encounters: List[GITEncounter] = field(default_factory=list)
    sounds:     List[GITSound]     = field(default_factory=list)
    stores:     List[GITStore]     = field(default_factory=list)
    _raw:       Optional[Dict]     = field(default=None, repr=False)

    @classmethod
    def from_bytes(cls, data: bytes) -> 'GITData':
        raw = GFFReader.from_bytes(data)
        if raw is None:
            return cls()
        g = cls(_raw=raw)

        def _f(d, key, default=0.0):
            v = d.get(key)
            try: return float(v) if v is not None else default
            except: return default

        def _s(d, key, default=''):
            v = d.get(key)
            return str(v) if v is not None else default

        def _i(d, key, default=0):
            v = d.get(key)
            try: return int(v) if v is not None else default
            except: return default

        def _v3(d, key, default=(0.0, 0.0, 0.0)):
            v = d.get(key)
            if isinstance(v, dict):
                return (_f(v, 'x', default[0]), _f(v, 'y', default[1]), _f(v, 'z', default[2]))
            if isinstance(v, (list, tuple)) and len(v) >= 3:
                return (_f({'v': v[0]}, 'v', default[0]), _f({'v': v[1]}, 'v', default[1]), _f({'v': v[2]}, 'v', default[2]))
            return default

        def _v4(d, key, default=(0.0, 0.0, 0.0, 1.0)):
            v = d.get(key)
            if isinstance(v, dict):
                return (_f(v, 'x', default[0]), _f(v, 'y', default[1]), _f(v, 'z', default[2]), _f(v, 'w', default[3]))
            if isinstance(v, (list, tuple)) and len(v) >= 4:
                return (
                    _f({'v': v[0]}, 'v', default[0]),
                    _f({'v': v[1]}, 'v', default[1]),
                    _f({'v': v[2]}, 'v', default[2]),
                    _f({'v': v[3]}, 'v', default[3]),
                )
            return default

        # Cameras
        for camera in (raw.get('CameraList') or []):
            if not isinstance(camera, dict): continue
            position = _v3(camera, 'Position')
            g.cameras.append(GITCamera(
                camera_id     = _i(camera, 'CameraID'),
                x             = position[0],
                y             = position[1],
                z             = position[2],
                orientation   = _v4(camera, 'Orientation'),
                field_of_view = _f(camera, 'FieldOfView'),
                height        = _f(camera, 'Height'),
                mic_range     = _f(camera, 'MicRange'),
                pitch         = _f(camera, 'Pitch'),
            ))

        # Creatures
        for c in (raw.get('Creature List') or []):
            if not isinstance(c, dict): continue
            g.creatures.append(GITCreature(
                resref  = _s(c, 'TemplateResRef'),
                x       = _f(c, 'XPosition'),
                y       = _f(c, 'YPosition'),
                z       = _f(c, 'ZPosition'),
                bearing = _f(c, 'XOrientation'),
            ))

        # Doors
        for d_raw in (raw.get('Door List') or []):
            if not isinstance(d_raw, dict): continue
            g.doors.append(GITDoor(
                resref            = _s(d_raw, 'TemplateResRef'),
                tag               = _s(d_raw, 'Tag'),
                x                 = _f(d_raw, 'X'),
                y                 = _f(d_raw, 'Y'),
                z                 = _f(d_raw, 'Z'),
                bearing           = _f(d_raw, 'Bearing'),
                linked_to         = _s(d_raw, 'LinkedTo'),
                linked_to_module  = _s(d_raw, 'LinkedToModule'),
                transition        = _i(d_raw, 'TransitionDestin'),
            ))

        # Placeables
        for p in (raw.get('Placeable List') or []):
            if not isinstance(p, dict): continue
            g.placeables.append(GITPlaceable(
                resref  = _s(p, 'TemplateResRef'),
                x       = _f(p, 'X'),
                y       = _f(p, 'Y'),
                z       = _f(p, 'Z'),
                bearing = _f(p, 'Bearing'),
            ))

        # Waypoints
        for w in (raw.get('WaypointList') or []):
            if not isinstance(w, dict): continue
            g.waypoints.append(GITWaypoint(
                resref  = _s(w, 'TemplateResRef'),
                tag     = _s(w, 'Tag'),
                x       = _f(w, 'XPosition'),
                y       = _f(w, 'YPosition'),
                z       = _f(w, 'ZPosition'),
                bearing = _f(w, 'XOrientation'),
            ))

        # Triggers
        for t in (raw.get('TriggerList') or []):
            if not isinstance(t, dict): continue
            geom = []
            for pt in (t.get('Geometry') or []):
                if isinstance(pt, dict):
                    geom.append((_f(pt,'PointX'), _f(pt,'PointY'), _f(pt,'PointZ')))
            g.triggers.append(GITTrigger(
                resref     = _s(t, 'TemplateResRef'),
                tag        = _s(t, 'Tag'),
                x          = _f(t, 'XPosition'),
                y          = _f(t, 'YPosition'),
                z          = _f(t, 'ZPosition'),
                geometry   = geom,
                linked_to  = _s(t, 'LinkedTo'),
                transition = _i(t, 'TransitionDestin'),
            ))

        # Encounters
        for e in (raw.get('Encounter List') or []):
            if not isinstance(e, dict): continue
            g.encounters.append(GITEncounter(
                resref = _s(e, 'TemplateResRef'),
                tag    = _s(e, 'Tag'),
                x      = _f(e, 'XPosition'),
                y      = _f(e, 'YPosition'),
                z      = _f(e, 'ZPosition'),
            ))

        # Sounds
        for s in (raw.get('SoundList') or []):
            if not isinstance(s, dict): continue
            g.sounds.append(GITSound(
                resref = _s(s, 'TemplateResRef'),
                tag    = _s(s, 'Tag'),
                x      = _f(s, 'XPosition'),
                y      = _f(s, 'YPosition'),
                z      = _f(s, 'ZPosition'),
            ))

        # Stores
        for store in (raw.get('StoreList') or []):
            if not isinstance(store, dict): continue
            g.stores.append(GITStore(
                resref = _s(store, 'TemplateResRef'),
                tag    = _s(store, 'Tag'),
            ))

        return g

    def summary(self) -> str:
        return (f"GIT: {len(self.cameras)} cameras, {len(self.creatures)} creatures, {len(self.doors)} doors, "
                f"{len(self.placeables)} placeables, {len(self.waypoints)} waypoints, "
                f"{len(self.triggers)} triggers, {len(self.encounters)} encounters, "
                f"{len(self.sounds)} sounds, {len(self.stores)} stores")


# ─────────────────────────────────────────────────────────────────────────────
#  IFO  (Module Info GFF)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class IFOData:
    tag:         str   = ""
    mod_name:    str   = ""
    entry_area:  str   = ""
    entry_x:     float = 0.0
    entry_y:     float = 0.0
    entry_z:     float = 0.0
    entry_dir_x: float = 1.0
    entry_dir_y: float = 0.0
    dawn_hour:   int   = 6
    dusk_hour:   int   = 20
    _raw:        Optional[Dict] = field(default=None, repr=False)

    @classmethod
    def from_bytes(cls, data: bytes) -> 'IFOData':
        raw = GFFReader.from_bytes(data)
        if raw is None:
            return cls()
        ifo = cls(_raw=raw)

        def _s(key, default=''):
            v = raw.get(key)
            if isinstance(v, dict):
                return v.get('strings', {}).get(0, default) or default
            return str(v) if v is not None else default

        def _f(key, default=0.0):
            v = raw.get(key)
            try: return float(v) if v is not None else default
            except: return default

        def _i(key, default=0):
            v = raw.get(key)
            try: return int(v) if v is not None else default
            except: return default

        ifo.tag        = _s('Mod_Tag', '')
        ifo.mod_name   = _s('Mod_Name', '')
        ifo.entry_area = _s('Mod_Entry_Area', '')
        ifo.entry_x    = _f('Mod_Entry_X')
        ifo.entry_y    = _f('Mod_Entry_Y')
        ifo.entry_z    = _f('Mod_Entry_Z')
        ifo.entry_dir_x = _f('Mod_Entry_Dir_X', 1.0)
        ifo.entry_dir_y = _f('Mod_Entry_Dir_Y', 0.0)
        ifo.dawn_hour  = _i('Mod_DawnHour', 6)
        ifo.dusk_hour  = _i('Mod_DuskHour', 20)
        return ifo


# ─────────────────────────────────────────────────────────────────────────────
#  WOK  (Walkmesh binary)
# ─────────────────────────────────────────────────────────────────────────────

# KotOR walkmesh surface material IDs
WOK_SURFACE_NAMES = {
    0: 'INVALID',
    1: 'DIRT',
    2: 'OBSCURING',
    3: 'GRASS',
    4: 'STONE',
    5: 'WOOD',
    6: 'WATER',
    7: 'NON_WALK',       # Wall / blocker (camera + movement blocked)
    8: 'TRANSPARENT',
    9: 'CARPET',
    10: 'METAL',
    11: 'PUDDLES',
    12: 'SWAMP',
    13: 'MUD',
    14: 'LEAVES',
    15: 'LAVA',
    16: 'BOTTOMLESS_PIT',
    17: 'DEEP_WATER',
    18: 'DOOR',          # walkable door surface
    19: 'SNOW',
    20: 'SAND',
    21: 'BAREBONES',
}

NON_WALK_ID   = 7
WALKABLE_IDS  = {1,3,4,5,9,10,11,12,13,14,19,20,21}  # materials NPCs can traverse

@dataclass
class WOKFace:
    v1: int
    v2: int
    v3: int
    surface: int        # material ID
    adj1: int = -1      # adjacent face index (or -1)
    adj2: int = -1
    adj3: int = -1

@dataclass
class WOKData:
    name:     str            = ""
    verts:    List[Tuple[float,float,float]] = field(default_factory=list)
    faces:    List[WOKFace]  = field(default_factory=list)
    raw:      Optional[bytes] = field(default=None, repr=False)

    # ── Parser ──────────────────────────────────────────────────────────────

    @classmethod
    def from_bytes(cls, data: bytes) -> 'WOKData':
        if len(data) < 136:
            return cls(raw=data)
        if data[:4] not in (b'BWM ', b'BWM\x20'):
            log.warning("WOK parse skipped: invalid BWM signature %r", data[:8])
            return cls(raw=data)
        try:
            return cls._from_pykotor_bwm(data)
        except Exception as exc:
            log.debug("PyKotor BWM parse unavailable; falling back to legacy WOK parser: %s", exc)
        wok = cls(raw=data)
        try:
            wok._parse(data)
        except Exception as e:
            log.warning(f"WOK parse error: {e}")
        return wok

    @classmethod
    def _from_pykotor_bwm(cls, data: bytes) -> 'WOKData':
        from pykotor.resource.formats.bwm import read_bwm  # type: ignore

        bwm = read_bwm(data)
        vertices = list(bwm.vertices())
        wok = cls(raw=data)
        wok.verts = [(float(v.x), float(v.y), float(v.z)) for v in vertices]
        index_by_id = {id(v): i for i, v in enumerate(vertices)}
        index_by_xyz = {
            (round(float(v.x), 6), round(float(v.y), 6), round(float(v.z), 6)): i
            for i, v in enumerate(vertices)
        }
        face_by_id = {id(face): i for i, face in enumerate(getattr(bwm, "faces", []) or [])}

        def vertex_index(vertex) -> int:
            idx = index_by_id.get(id(vertex))
            if idx is not None:
                return idx
            return index_by_xyz.get(
                (round(float(vertex.x), 6), round(float(vertex.y), 6), round(float(vertex.z), 6)),
                0,
            )

        def face_index(value) -> int:
            if value is None:
                return -1
            if isinstance(value, int):
                return value
            return face_by_id.get(id(value), -1)

        for face in getattr(bwm, "faces", []) or []:
            wok.faces.append(
                WOKFace(
                    vertex_index(face.v1),
                    vertex_index(face.v2),
                    vertex_index(face.v3),
                    int(getattr(face, "material", 0) or 0),
                    face_index(getattr(face, "trans1", None)),
                    face_index(getattr(face, "trans2", None)),
                    face_index(getattr(face, "trans3", None)),
                )
            )
        return wok

    @classmethod
    def from_file(cls, path: str) -> 'WOKData':
        return cls.from_bytes(Path(path).read_bytes())

    def _parse(self, d: bytes):
        # BWM header (136 bytes)
        sig = d[:4]
        if sig not in (b'BWM ', b'BWM\x20'):
            raise ValueError(f"Invalid WOK/BWM signature: {sig!r}")
        ver = d[4:8]

        vert_count = struct.unpack_from('<I', d, 56)[0]
        vert_off   = struct.unpack_from('<I', d, 60)[0]
        face_count = struct.unpack_from('<I', d, 64)[0]
        face_off   = struct.unpack_from('<I', d, 68)[0]
        mat_off    = struct.unpack_from('<I', d, 72)[0]
        adj_off    = struct.unpack_from('<I', d, 76)[0]
        if vert_count > 1_000_000 or face_count > 1_000_000:
            raise ValueError(f"Unreasonable WOK counts: verts={vert_count}, faces={face_count}")
        if vert_off + vert_count * 12 > len(d):
            raise ValueError("WOK vertex array extends past end of data")
        if face_off + face_count * 6 > len(d):
            raise ValueError("WOK face array extends past end of data")

        # Vertices (3 floats each)
        for i in range(vert_count):
            off = vert_off + i * 12
            if off + 12 <= len(d):
                x, y, z = struct.unpack_from('<fff', d, off)
                self.verts.append((x, y, z))

        # Faces (3 uint16 vertex indices each)
        # Material IDs are in a parallel array
        for i in range(face_count):
            foff = face_off + i * 6
            moff = mat_off  + i * 4
            aoff = adj_off  + i * 12
            if foff + 6 > len(d):
                break
            v1, v2, v3 = struct.unpack_from('<HHH', d, foff)
            surf = struct.unpack_from('<I', d, moff)[0] if moff + 4 <= len(d) else 0
            a1   = struct.unpack_from('<i', d, aoff)[0]   if aoff +  4 <= len(d) else -1
            a2   = struct.unpack_from('<i', d, aoff+4)[0] if aoff +  8 <= len(d) else -1
            a3   = struct.unpack_from('<i', d, aoff+8)[0] if aoff + 12 <= len(d) else -1
            self.faces.append(WOKFace(v1, v2, v3, surf, a1, a2, a3))

    # ── Helpers ──────────────────────────────────────────────────────────────

    def walkable_face_count(self) -> int:
        return sum(1 for f in self.faces if f.surface in WALKABLE_IDS)

    def non_walk_face_count(self) -> int:
        return sum(1 for f in self.faces if f.surface == NON_WALK_ID)

    def boundary_edges(self) -> List[Tuple[int,int,int,int]]:
        """
        Return edges that border a walkable face on one side and either
        a non-walk / missing (boundary) face on the other.

        Returns list of (va, vb, face_idx, edge_idx).
        """
        edges = []
        for fi, face in enumerate(self.faces):
            if face.surface not in WALKABLE_IDS:
                continue
            verts_idx = (face.v1, face.v2, face.v3)
            adjs = (face.adj1, face.adj2, face.adj3)
            for ei in range(3):
                adj = adjs[ei]
                if adj == -1 or (adj < len(self.faces) and
                                  self.faces[adj].surface not in WALKABLE_IDS):
                    va = verts_idx[ei]
                    vb = verts_idx[(ei+1) % 3]
                    edges.append((va, vb, fi, ei))
        return edges

    def summary(self) -> str:
        return (f"WOK: {len(self.verts)} verts, {len(self.faces)} faces, "
                f"{self.walkable_face_count()} walkable, "
                f"{self.non_walk_face_count()} non-walk")

    # ── Editing helpers ───────────────────────────────────────────────────────

    def set_face_surface(self, face_idx: int, surface_id: int) -> bool:
        """Change the surface material of a single face.  Returns True on success."""
        if face_idx < 0 or face_idx >= len(self.faces):
            return False
        f = self.faces[face_idx]
        self.faces[face_idx] = WOKFace(f.v1, f.v2, f.v3, surface_id, f.adj1, f.adj2, f.adj3)
        return True

    def bulk_replace_surface(self, src_id: int, dst_id: int) -> int:
        """Replace all faces with surface_id==src_id with dst_id.  Returns count changed."""
        count = 0
        for i, f in enumerate(self.faces):
            if f.surface == src_id:
                self.faces[i] = WOKFace(f.v1, f.v2, f.v3, dst_id, f.adj1, f.adj2, f.adj3)
                count += 1
        return count

    def surface_distribution(self) -> Dict[int, int]:
        """Return {surface_id: face_count} mapping."""
        dist: Dict[int, int] = {}
        for f in self.faces:
            dist[f.surface] = dist.get(f.surface, 0) + 1
        return dist

    def face_at_point(self, px: float, py: float) -> int:
        """
        Return index of the first face whose 2-D (XY) projection contains
        the point (px, py), or -1 if none found.  Used by the walkmesh paint brush.
        """
        for fi, face in enumerate(self.faces):
            if face.v1 >= len(self.verts) or face.v2 >= len(self.verts) or face.v3 >= len(self.verts):
                continue
            ax, ay = self.verts[face.v1][0], self.verts[face.v1][1]
            bx, by = self.verts[face.v2][0], self.verts[face.v2][1]
            cx, cy = self.verts[face.v3][0], self.verts[face.v3][1]
            # Sign-of-cross-product test (point-in-triangle 2D)
            def _sign(x1, y1, x2, y2, x3, y3):
                return (x1 - x3) * (y2 - y3) - (x2 - x3) * (y1 - y3)
            d1 = _sign(px, py, ax, ay, bx, by)
            d2 = _sign(px, py, bx, by, cx, cy)
            d3 = _sign(px, py, cx, cy, ax, ay)
            has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
            has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
            if not (has_neg and has_pos):
                return fi
        return -1

    # ── Binary serialisation ──────────────────────────────────────────────────

    def to_bytes(self) -> bytes:
        """
        Serialise the WOKData back to a valid Aurora BWM binary blob.

        Area WOKs need more than vertices/faces/materials: the engine expects
        normals, plane coefficients, AABB nodes, adjacency, perimeter edges, and
        perimeter loop records.  Use PyKotor's BWM writer as the canonical
        serializer instead of maintaining a partial duplicate here.
        """
        import io

        from pykotor.resource.formats.bwm import write_bwm
        from pykotor.resource.formats.bwm.bwm_data import BWM, BWMFace, BWMType
        from utility.common.geometry import SurfaceMaterial, Vector3

        class _NonClosingBytesIO(io.BytesIO):
            def close(self):  # type: ignore[override]
                self.flush()

        bwm = BWM()
        bwm.walkmesh_type = BWMType.AreaModel
        vertices = [Vector3(x, y, z) for x, y, z in self.verts]
        for face in self.faces:
            try:
                v1, v2, v3 = vertices[face.v1], vertices[face.v2], vertices[face.v3]
            except IndexError as exc:
                raise ValueError(
                    f"WOK face references missing vertex: "
                    f"{face.v1}, {face.v2}, {face.v3}"
                ) from exc
            bwm_face = BWMFace(v1, v2, v3)
            try:
                bwm_face.material = SurfaceMaterial(int(face.surface))
            except ValueError:
                bwm_face.material = SurfaceMaterial.UNDEFINED
            # WOKFace.adj* stores geometric adjacency in GhostRigger's light
            # editor model.  BWMFace.trans* is a door/area transition index, not
            # adjacency, so leave it empty and let PyKotor derive adjacency and
            # perimeter records from the geometry.
            bwm.faces.append(bwm_face)

        output = _NonClosingBytesIO()
        write_bwm(bwm, output)
        return output.getvalue()

    def write_binary(self, path: str):
        """Write the WOKData to a binary .wok file at *path*."""
        Path(path).write_bytes(self.to_bytes())
        log.info("WOKData.write_binary → %s  (%d verts, %d faces)", path, len(self.verts), len(self.faces))


# ─────────────────────────────────────────────────────────────────────────────
#  Walkmesh Wall Auto-Generator
# ─────────────────────────────────────────────────────────────────────────────

class WalkmeshWallGenerator:
    """
    Automatically generate vertical NON_WALK wall quads along the boundary
    edges of the walkable area in a WOKData object.

    This solves the infamous "Quanon modules camera clips through walls" problem.
    The engine checks walkmesh NON_WALK faces for camera + LOS blocking.

    Algorithm:
      1. Find all boundary edges of walkable faces
         (edges adjacent to NON_WALK or missing adjacency)
      2. For each such edge, extrude the two vertices upward by wall_height
      3. Create two triangles (a quad) with surface = NON_WALK_ID = 7
      4. Append new vertices and faces to the WOKData
    """

    def __init__(self, wall_height: float = 3.0, deduplicate: bool = True):
        self.wall_height  = wall_height
        self.deduplicate  = deduplicate

    def generate(self, wok: WOKData, progress_cb=None) -> WOKData:
        """
        Return a NEW WOKData with wall quads added.
        Does not modify the input.
        """
        import copy
        new_wok = copy.deepcopy(wok)
        new_wok.raw = None  # will be rebuilt

        boundary = wok.boundary_edges()
        if not boundary:
            log.info("WalkmeshWallGenerator: no boundary edges found")
            return new_wok

        total = len(boundary)
        log.info(f"WalkmeshWallGenerator: generating {total} wall quads "
                 f"(height={self.wall_height:.1f}m)")

        # Vertex dedup cache: (x,y,z) → new index
        vert_cache: Dict[Tuple[float,float,float], int] = {}
        def _add_vert(xyz) -> int:
            key = (round(xyz[0],4), round(xyz[1],4), round(xyz[2],4))
            if self.deduplicate and key in vert_cache:
                return vert_cache[key]
            idx = len(new_wok.verts)
            new_wok.verts.append(xyz)
            vert_cache[key] = idx
            return idx

        for i, (va, vb, fi, ei) in enumerate(boundary):
            if va >= len(wok.verts) or vb >= len(wok.verts):
                continue

            x1, y1, z1 = wok.verts[va]
            x2, y2, z2 = wok.verts[vb]
            h = self.wall_height

            # Bottom edge (on the ground)
            bi1 = _add_vert((x1, y1, z1))
            bi2 = _add_vert((x2, y2, z2))
            # Top edge (extruded upward)
            ti1 = _add_vert((x1, y1, z1 + h))
            ti2 = _add_vert((x2, y2, z2 + h))

            # Triangle 1: bottom-left, bottom-right, top-right
            new_wok.faces.append(WOKFace(bi1, bi2, ti2, NON_WALK_ID))
            # Triangle 2: bottom-left, top-right, top-left
            new_wok.faces.append(WOKFace(bi1, ti2, ti1, NON_WALK_ID))

            if progress_cb and i % 50 == 0:
                progress_cb(i / total)

        added_faces  = len(new_wok.faces) - len(wok.faces)
        added_verts  = len(new_wok.verts) - len(wok.verts)
        log.info(f"WalkmeshWallGenerator: added {added_faces} faces, "
                 f"{added_verts} new vertices")
        return new_wok

    def write_ascii_wok(self, wok: WOKData, path: str):
        """
        Write a Walkmesh in simple ASCII format that can be imported into
        Blender / 3DS Max via KBlender / NWMax for further editing.
        """
        lines = [
            "# KOTOR ASCII Walkmesh – generated by GhostRigger Modular Mode",
            f"# vertices: {len(wok.verts)}  faces: {len(wok.faces)}",
            f"verts {len(wok.verts)}",
        ]
        for v in wok.verts:
            lines.append(f"  {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}")
        lines.append(f"faces {len(wok.faces)}")
        for f in wok.faces:
            lines.append(f"  {f.v1} {f.v2} {f.v3} {f.surface}")
        Path(path).write_text("\n".join(lines) + "\n", encoding='ascii')


# ─────────────────────────────────────────────────────────────────────────────
#  Module – high-level container
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class KotorModule:
    """
    A complete parsed KOTOR module.
    Can be loaded from a .mod / .rim / .erf archive or from loose Override files.
    """
    name:    str         = ""
    game:    str         = "K1"   # 'K1' or 'K2'
    lyt:     Optional[LYTLayout]  = None
    vis:     Optional[VISData]    = None
    are:     Optional[AREData]    = None
    git:     Optional[GITData]    = None
    ifo:     Optional[IFOData]    = None
    wok:     Optional[WOKData]    = None
    # additional WOKs (one per room model)
    room_woks: Dict[str, WOKData] = field(default_factory=dict)
    # raw resource bytes cache  resref.lower() → bytes
    resources: Dict[str, bytes]   = field(default_factory=dict)

    @classmethod
    def from_directory(cls, directory: str, module_name: str = "",
                       game: str = "K1") -> 'KotorModule':
        """
        Load a module from a directory of loose files (Override / extracted).
        Files expected: <module_name>.lyt, .vis, .are, .git, .ifo, .wok
        """
        d = Path(directory)
        mod = cls(name=module_name, game=game)

        # Auto-detect module name from directory if not supplied
        if not module_name:
            lyt_files = list(d.glob("*.lyt"))
            if lyt_files:
                module_name = lyt_files[0].stem
                mod.name = module_name

        if not module_name:
            return mod

        def _load(ext) -> Optional[bytes]:
            p = d / f"{module_name}{ext}"
            if p.exists():
                return p.read_bytes()
            # case-insensitive fallback
            for f in d.iterdir():
                if f.suffix.lower() == ext and f.stem.lower() == module_name.lower():
                    return f.read_bytes()
            return None

        lyt_text_path = d / f"{module_name}.lyt"
        vis_text_path = d / f"{module_name}.vis"
        if lyt_text_path.exists():
            mod.lyt = LYTLayout.from_file(str(lyt_text_path))
        if vis_text_path.exists():
            mod.vis = VISData.from_file(str(vis_text_path))

        are_bytes = _load(".are")
        if are_bytes:
            mod.are = AREData.from_bytes(are_bytes)
        git_bytes = _load(".git")
        if git_bytes:
            mod.git = GITData.from_bytes(git_bytes)
        ifo_bytes = _load(".ifo")
        if ifo_bytes:
            mod.ifo = IFOData.from_bytes(ifo_bytes)
        wok_bytes = _load(".wok")
        if wok_bytes:
            mod.wok = WOKData.from_bytes(wok_bytes)

        # Load per-room WOKs (named like <roommodel>.wok)
        if mod.lyt:
            for room in mod.lyt.rooms:
                p = d / f"{room.model}.wok"
                if p.exists():
                    mod.room_woks[room.model] = WOKData.from_bytes(p.read_bytes())

        return mod

    def summary(self) -> str:
        lines = [f"Module: {self.name!r} ({self.game})"]
        if self.lyt:
            lines.append(f"  LYT: {len(self.lyt.rooms)} rooms, "
                         f"{len(self.lyt.doorhooks)} doorhooks")
        if self.vis:
            lines.append(f"  VIS: {len(self.vis.visibility)} room entries")
        if self.git:
            lines.append(f"  {self.git.summary()}")
        if self.are:
            lines.append(f"  ARE: {self.are.name!r}")
        if self.ifo:
            lines.append(f"  IFO: entry={self.ifo.entry_area}")
        if self.wok:
            lines.append(f"  {self.wok.summary()}")
        for rname, rwok in self.room_woks.items():
            lines.append(f"  WOK[{rname}]: {rwok.summary()}")
        return "\n".join(lines)
