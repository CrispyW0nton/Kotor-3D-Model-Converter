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
    #: Room model the hook belongs to.  Vanilla LYT doorhook lines are
    #: "room door_name 0 x y z qw qx qy qz" — the engine sscanf's that exact
    #: shape; emitting fewer tokens crashed swkotor2 (strlen AV in vscan_fn,
    #: live session 20260708-114626-runtime-test-plcaa-k2-warp).
    room: str = ""

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

            # Parse doorhook entry.  Supported shapes:
            #   vanilla:      room door_name 0 x y z qw qx qy qz   (10 tokens)
            #   KotorBlender: room door_name x y z qx qy qz qw     (9 tokens)
            #   legacy:       name x y z [qx qy qz qw]
            if state == 'doorhookcount':
                try:
                    second_is_number = True
                    try:
                        float(tokens[1])
                    except (IndexError, ValueError):
                        second_is_number = False
                    if not second_is_number and len(tokens) >= 6:
                        room_name = tokens[0].lower()
                        door_name = tokens[1].lower()
                        nums = [float(value) for value in tokens[2:]]
                        if len(nums) >= 8:
                            # vanilla: flag, pos, then quat stored w-first
                            dx, dy, dz = nums[1], nums[2], nums[3]
                            qw, qx, qy, qz = nums[4], nums[5], nums[6], nums[7]
                        else:
                            dx, dy, dz = nums[0], nums[1], nums[2]
                            qx = nums[3] if len(nums) > 3 else 0.0
                            qy = nums[4] if len(nums) > 4 else 0.0
                            qz = nums[5] if len(nums) > 5 else 0.0
                            qw = nums[6] if len(nums) > 6 else 1.0
                        lyt.doorhooks.append(LYTDoorHook(
                            door_name, dx, dy, dz, qx, qy, qz, qw, room=room_name))
                    else:
                        dx, dy, dz = float(tokens[1]), float(tokens[2]), float(tokens[3])
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
        lines.append(f"   roomcount {len(self.rooms)}")
        for r in self.rooms:
            lines.append(f"      {r.model} {r.x:.6f} {r.y:.6f} {r.z:.6f}")
        lines.append("   trackcount 0")
        lines.append("   obstaclecount 0")
        lines.append(f"   doorhookcount {len(self.doorhooks)}")
        default_room = self.rooms[0].model if self.rooms else "room"
        for d in self.doorhooks:
            # Engine contract (vanilla 101PER/202TEL, and the crash it fixes:
            # sscanf/strlen AV when tokens are missing): every doorhook line
            # is "room door_name 0 x y z qw qx qy qz".
            room = d.room or default_room
            lines.append(
                f"      {room} {d.name} 0 {d.x:.6f} {d.y:.6f} {d.z:.6f} "
                f"{d.qw:.6f} {d.qx:.6f} {d.qy:.6f} {d.qz:.6f}"
            )
        lines.append("donelayout")
        # Vanilla LYT/VIS are CRLF text; match them byte-for-byte.
        return "\r\n".join(lines) + "\r\n"

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
        # Vanilla VIS files are CRLF text; match them.
        return "\r\n".join(lines) + "\r\n"

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
    linked_to_flags: int = 0
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
    linked_to_module: str = ""
    linked_to_flags: int = 0
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
            if isinstance(v, dict):
                v = v.get('strref', v.get('stringref', v.get('value')))
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
                bearing = math.atan2(_f(c, 'YOrientation'), _f(c, 'XOrientation', 1.0)),
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
                linked_to_flags   = _i(d_raw, 'LinkedToFlags'),
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
                linked_to_module = _s(t, 'LinkedToModule'),
                linked_to_flags = _i(t, 'LinkedToFlags'),
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

        # Stores: engine contract is "ResRef" (vanilla 202TEL GIT); older
        # authored payloads may still carry "TemplateResRef".
        for store in (raw.get('StoreList') or []):
            if not isinstance(store, dict): continue
            g.stores.append(GITStore(
                resref = _s(store, 'ResRef') or _s(store, 'TemplateResRef'),
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
    19: 'NON_WALK_GRASS',
    20: 'SURFACE_MATERIAL_20',
    21: 'SURFACE_MATERIAL_21',
    22: 'SURFACE_MATERIAL_22',
    23: 'SURFACE_MATERIAL_23',
    24: 'SURFACE_MATERIAL_24',
    25: 'SURFACE_MATERIAL_25',
    26: 'SURFACE_MATERIAL_26',
    27: 'SURFACE_MATERIAL_27',
    28: 'SURFACE_MATERIAL_28',
    29: 'SURFACE_MATERIAL_29',
    30: 'TRIGGER',
}

NON_WALK_ID   = 7
WALKABLE_IDS  = {1,3,4,5,6,9,10,11,12,13,14,18,30}  # canonical Odyssey walkable materials

@dataclass
class WOKFace:
    v1: int
    v2: int
    v3: int
    surface: int        # material ID
    adj1: int = -1      # adjacent face index (or -1)
    adj2: int = -1
    adj3: int = -1
    trans1: int = -1    # door/area transition index for each directed edge
    trans2: int = -1
    trans3: int = -1

@dataclass
class WOKData:
    name:     str            = ""
    verts:    List[Tuple[float,float,float]] = field(default_factory=list)
    faces:    List[WOKFace]  = field(default_factory=list)
    raw:      Optional[bytes] = field(default=None, repr=False)
    relative_hook1: Tuple[float,float,float] = (0.0, 0.0, 0.0)
    relative_hook2: Tuple[float,float,float] = (0.0, 0.0, 0.0)
    absolute_hook1: Tuple[float,float,float] = (0.0, 0.0, 0.0)
    absolute_hook2: Tuple[float,float,float] = (0.0, 0.0, 0.0)
    position: Tuple[float,float,float] = (0.0, 0.0, 0.0)
    adjacency_domain_count: Optional[int] = None

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

        # Keep PyKotor as the independent format validator, but do not build
        # Ghost Studio's topology from ``BWM.vertices()``: that API deduplicates
        # value-equal Vector3 objects and erases intentional retail index seams.
        read_bwm(data)
        wok = cls(raw=data)
        wok._parse(data)
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

        self.relative_hook1 = struct.unpack_from('<3f', d, 12)
        self.relative_hook2 = struct.unpack_from('<3f', d, 24)
        self.absolute_hook1 = struct.unpack_from('<3f', d, 36)
        self.absolute_hook2 = struct.unpack_from('<3f', d, 48)
        self.position = struct.unpack_from('<3f', d, 60)
        vert_count = struct.unpack_from('<I', d, 72)[0]
        vert_off   = struct.unpack_from('<I', d, 76)[0]
        face_count = struct.unpack_from('<I', d, 80)[0]
        face_off   = struct.unpack_from('<I', d, 84)[0]
        mat_off    = struct.unpack_from('<I', d, 88)[0]
        adj_count  = struct.unpack_from('<I', d, 112)[0]
        self.adjacency_domain_count = adj_count
        adj_off    = struct.unpack_from('<I', d, 116)[0]
        if vert_count > 1_000_000 or face_count > 1_000_000:
            raise ValueError(f"Unreasonable WOK counts: verts={vert_count}, faces={face_count}")
        if vert_off + vert_count * 12 > len(d):
            raise ValueError("WOK vertex array extends past end of data")
        if face_off + face_count * 12 > len(d):
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
            foff = face_off + i * 12
            moff = mat_off  + i * 4
            aoff = adj_off  + i * 12
            if foff + 12 > len(d):
                break
            v1, v2, v3 = struct.unpack_from('<III', d, foff)
            surf = struct.unpack_from('<I', d, moff)[0] if moff + 4 <= len(d) else 0
            has_adjacency = i < adj_count
            raw_a1 = struct.unpack_from('<i', d, aoff)[0]   if has_adjacency and aoff +  4 <= len(d) else -1
            raw_a2 = struct.unpack_from('<i', d, aoff+4)[0] if has_adjacency and aoff +  8 <= len(d) else -1
            raw_a3 = struct.unpack_from('<i', d, aoff+8)[0] if has_adjacency and aoff + 12 <= len(d) else -1
            # Odyssey stores the neighboring directed edge (face*3+edge),
            # while WOKFace exposes the adjacent face index to authoring code.
            a1 = -1 if raw_a1 < 0 else raw_a1 // 3
            a2 = -1 if raw_a2 < 0 else raw_a2 // 3
            a3 = -1 if raw_a3 < 0 else raw_a3 // 3
            self.faces.append(WOKFace(v1, v2, v3, surf, a1, a2, a3))

        # Door/area transitions live in the perimeter edge table, indexed by
        # the source directed edge.  Preserve them independently of geometric
        # adjacency.
        edge_count, edge_off = struct.unpack_from('<II', d, 120)
        if edge_off + edge_count * 8 > len(d):
            raise ValueError("WOK transition edge array extends past end of data")
        for edge_index in range(edge_count):
            directed_edge, transition = struct.unpack_from('<ii', d, edge_off + edge_index * 8)
            if transition < 0 or directed_edge < 0:
                continue
            face_index, local_edge = divmod(directed_edge, 3)
            if face_index >= len(self.faces):
                raise ValueError(f"WOK transition references missing face edge {directed_edge}")
            setattr(self.faces[face_index], f"trans{local_edge + 1}", transition)

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

    def rebuild_adjacencies(self) -> None:
        """Rebuild geometric face adjacency without conflating transitions."""

        owners: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
        for face_index, face in enumerate(self.faces):
            face.adj1 = face.adj2 = face.adj3 = -1
            triangle = (face.v1, face.v2, face.v3)
            for local_edge in range(3):
                key = tuple(sorted((triangle[local_edge], triangle[(local_edge + 1) % 3])))
                owners.setdefault(key, []).append((face_index, local_edge))
        for rows in owners.values():
            if len(rows) != 2:
                continue
            (face_a, edge_a), (face_b, edge_b) = rows
            setattr(self.faces[face_a], f"adj{edge_a + 1}", face_b)
            setattr(self.faces[face_b], f"adj{edge_b + 1}", face_a)

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
        self.faces[face_idx] = WOKFace(
            f.v1, f.v2, f.v3, surface_id, f.adj1, f.adj2, f.adj3, f.trans1, f.trans2, f.trans3
        )
        return True

    def bulk_replace_surface(self, src_id: int, dst_id: int) -> int:
        """Replace all faces with surface_id==src_id with dst_id.  Returns count changed."""
        count = 0
        for i, f in enumerate(self.faces):
            if f.surface == src_id:
                self.faces[i] = WOKFace(
                    f.v1, f.v2, f.v3, dst_id, f.adj1, f.adj2, f.adj3, f.trans1, f.trans2, f.trans3
                )
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
        """Serialize one engine-complete, index-stable area BWM.

        Unchanged imported WOKs return their exact source bytes.  Edited and
        generated WOKs use Ghost Studio's linear-time indexed writer; PyKotor's
        value-equality adjacency and repeated linear identity searches are not
        used because they both erase intentional seams and become quadratic on
        practical rooms.
        """

        if self.raw is not None and _wok_semantically_matches_raw(self, self.raw):
            return bytes(self.raw)
        return _serialize_wok_data(self, source_raw=self.raw)

    def write_binary(self, path: str):
        """Write the WOKData to a binary .wok file at *path*."""
        Path(path).write_bytes(self.to_bytes())
        log.info("WOKData.write_binary → %s  (%d verts, %d faces)", path, len(self.verts), len(self.faces))


def _wok_semantically_matches_raw(wok: WOKData, data: bytes) -> bool:
    """Return whether ``wok`` is still index-identical to its source BWM.

    BWM topology is defined by vertex-table and face-index identity, not by
    coincident corner coordinates.  In particular, retail walkmeshes use
    duplicate-coordinate vertices to preserve intentional collision seams.
    Reusing ``raw`` after an edit redirects a face to such a duplicate would
    silently discard that edit, so the raw fast path deliberately compares the
    complete indexed topology and adjacency domain.
    """

    if len(data) < 136 or data[:8] != b"BWM V1.0":
        return False
    try:
        raw_hooks = struct.unpack_from("<15f", data, 12)
        current_hooks = tuple(
            float(value)
            for vector in (
                wok.relative_hook1,
                wok.relative_hook2,
                wok.absolute_hook1,
                wok.absolute_hook2,
                wok.position,
            )
            for value in vector
        )
        if len(current_hooks) != 15 or any(abs(left - right) > 1.0e-5 for left, right in zip(raw_hooks, current_hooks)):
            return False
        vertex_count, vertex_offset, face_count, face_offset, material_offset = struct.unpack_from("<IIIII", data, 72)
        raw_adjacency_count, raw_adjacency_offset = struct.unpack_from("<II", data, 112)
        edge_count, edge_offset = struct.unpack_from("<II", data, 120)
        if vertex_count != len(wok.verts) or face_count != len(wok.faces):
            return False
        if wok.adjacency_domain_count is None or int(wok.adjacency_domain_count) != raw_adjacency_count:
            return False
        if (
            vertex_offset + vertex_count * 12 > len(data)
            or face_offset + face_count * 12 > len(data)
            or material_offset + face_count * 4 > len(data)
            or raw_adjacency_offset + raw_adjacency_count * 12 > len(data)
            or edge_offset + edge_count * 8 > len(data)
        ):
            return False

        # Compare the exact float32 vertex table, including unused and
        # coincident entries.  Comparing only face-corner coordinates loses
        # index seams and can also miss an added unused vertex.
        for vertex_index, vertex in enumerate(wok.verts):
            if len(vertex) != 3:
                return False
            try:
                current_row = struct.pack("<3f", *(float(value) for value in vertex))
            except (OverflowError, TypeError, ValueError, struct.error):
                return False
            raw_offset = vertex_offset + vertex_index * 12
            if current_row != data[raw_offset : raw_offset + 12]:
                return False

        transitions: dict[int, int] = {}
        for index in range(edge_count):
            edge_id, transition = struct.unpack_from("<ii", data, edge_offset + index * 8)
            if transition >= 0:
                if edge_id < 0 or edge_id >= face_count * 3 or edge_id in transitions:
                    return False
                transitions[edge_id] = transition

        for face_index, face in enumerate(wok.faces):
            raw_indices = struct.unpack_from("<III", data, face_offset + face_index * 12)
            current_indices = (int(face.v1), int(face.v2), int(face.v3))
            if current_indices != raw_indices or any(index >= vertex_count for index in raw_indices):
                return False
            if struct.unpack_from("<I", data, material_offset + face_index * 4)[0] != int(face.surface):
                return False
            current_transitions = (int(face.trans1), int(face.trans2), int(face.trans3))
            if any(transitions.get(face_index * 3 + edge_index, -1) != current_transitions[edge_index] for edge_index in range(3)):
                return False

            if face_index >= raw_adjacency_count:
                continue
            raw_adjacency = struct.unpack_from("<iii", data, raw_adjacency_offset + face_index * 12)
            current_adjacency = (int(face.adj1), int(face.adj2), int(face.adj3))
            for local_edge, raw_edge_id in enumerate(raw_adjacency):
                if raw_edge_id < 0:
                    if current_adjacency[local_edge] != -1:
                        return False
                    continue
                adjacent_face, adjacent_edge = divmod(raw_edge_id, 3)
                if adjacent_face >= raw_adjacency_count or current_adjacency[local_edge] != adjacent_face:
                    return False
                adjacent = wok.faces[adjacent_face]
                adjacent_indices = (int(adjacent.v1), int(adjacent.v2), int(adjacent.v3))
                source_start = current_indices[local_edge]
                source_end = current_indices[(local_edge + 1) % 3]
                if (
                    adjacent_indices[adjacent_edge] != source_end
                    or adjacent_indices[(adjacent_edge + 1) % 3] != source_start
                ):
                    return False
        return True
    except (IndexError, TypeError, ValueError, struct.error):
        return False


def _serialize_wok_data(wok: WOKData, *, source_raw: Optional[bytes]) -> bytes:
    """Write primary BWM tables once, then derive AABB/adjacency/perimeters."""

    vertices = [tuple(float(value) for value in vertex[:3]) for vertex in wok.verts]
    if any(len(vertex) != 3 or not all(math.isfinite(value) for value in vertex) for vertex in vertices):
        raise ValueError("WOK vertices must contain three finite coordinates.")
    if wok.adjacency_domain_count is None:
        ordered_faces = [face for face in wok.faces if int(face.surface) in WALKABLE_IDS]
        ordered_faces.extend(face for face in wok.faces if int(face.surface) not in WALKABLE_IDS)
        walkable_count = sum(int(face.surface) in WALKABLE_IDS for face in ordered_faces)
    else:
        ordered_faces = list(wok.faces)
        walkable_count = int(wok.adjacency_domain_count)
        if walkable_count < 0 or walkable_count > len(ordered_faces):
            raise ValueError(
                f"WOK adjacency domain {walkable_count} is outside its {len(ordered_faces)}-face table."
            )
    for face in ordered_faces:
        indices = (int(face.v1), int(face.v2), int(face.v3))
        if any(index < 0 or index >= len(vertices) for index in indices):
            raise ValueError(f"WOK face references missing vertex: {indices[0]}, {indices[1]}, {indices[2]}")

    buffer = bytearray(136)
    buffer[:8] = b"BWM V1.0"
    struct.pack_into("<I", buffer, 8, 1)
    hooks = tuple(
        float(value)
        for vector in (
            wok.relative_hook1,
            wok.relative_hook2,
            wok.absolute_hook1,
            wok.absolute_hook2,
            wok.position,
        )
        for value in vector
    )
    if len(hooks) != 15 or not all(math.isfinite(value) for value in hooks):
        raise ValueError("WOK hook and position vectors must contain fifteen finite values.")
    struct.pack_into("<15f", buffer, 12, *hooks)

    vertex_offset = len(buffer)
    for vertex in vertices:
        buffer += struct.pack("<3f", *vertex)
    face_offset = len(buffer)
    for face in ordered_faces:
        buffer += struct.pack("<III", int(face.v1), int(face.v2), int(face.v3))
    material_offset = len(buffer)
    for face in ordered_faces:
        buffer += struct.pack("<I", int(face.surface) & 0xFFFFFFFF)
    normal_offset = len(buffer)
    planes: list[float] = []
    for face in ordered_faces:
        a, b, c = vertices[int(face.v1)], vertices[int(face.v2)], vertices[int(face.v3)]
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx, ny, nz = (uy * vz) - (uz * vy), (uz * vx) - (ux * vz), (ux * vy) - (uy * vx)
        length = math.sqrt((nx * nx) + (ny * ny) + (nz * nz))
        normal = (1.0, 0.0, 0.0) if length <= 1.0e-12 else (nx / length, ny / length, nz / length)
        planes.append(-((normal[0] * a[0]) + (normal[1] * a[1]) + (normal[2] * a[2])))
        buffer += struct.pack("<3f", *normal)
    plane_offset = len(buffer)
    for plane in planes:
        buffer += struct.pack("<f", plane)

    aabb_offset = len(buffer)
    adjacency_offset = len(buffer)
    for _ in range(walkable_count):
        buffer += struct.pack("<iii", -1, -1, -1)
    edge_offset = len(buffer)
    transition_rows: list[tuple[int, int]] = []
    for face_index, face in enumerate(ordered_faces):
        for edge_index, transition in enumerate((face.trans1, face.trans2, face.trans3)):
            if int(transition) >= 0:
                transition_rows.append((face_index * 3 + edge_index, int(transition)))
    for edge_id, transition in transition_rows:
        buffer += struct.pack("<ii", edge_id, transition)
    perimeter_offset = len(buffer)
    struct.pack_into(
        "<16I",
        buffer,
        72,
        len(vertices),
        vertex_offset,
        len(ordered_faces),
        face_offset,
        material_offset,
        normal_offset,
        plane_offset,
        0,
        aabb_offset,
        0,
        walkable_count,
        adjacency_offset,
        len(transition_rows),
        edge_offset,
        0,
        perimeter_offset,
    )
    return _patch_bwm_perimeters(bytes(buffer), source_raw=source_raw)


def _rebuild_bwm_aabb_tree(data: bytes) -> bytes:
    """Replace PyKotor's lossy AABB tree with a complete index-stable tree.

    PyKotor collapses a group of faces that share one centroid into a single
    leaf. Vanilla ``m36aa_01`` demonstrates that this drops collision faces on
    round-trip. Odyssey's ordinary room contract is a preorder binary tree
    with one leaf per face and ``2F-1`` nodes. When every centroid is equal,
    split deterministically by face index instead of discarding faces.
    """

    if len(data) < 136:
        return data
    vertex_count, vertex_offset, face_count, face_offset = struct.unpack_from("<IIII", data, 72)
    old_aabb_count, old_aabb_offset = struct.unpack_from("<II", data, 100)
    adjacency_count, old_adjacency_offset = struct.unpack_from("<II", data, 112)
    edge_count, old_edge_offset = struct.unpack_from("<II", data, 120)
    perimeter_count, old_perimeter_offset = struct.unpack_from("<II", data, 128)
    if not face_count:
        return data
    if (
        vertex_offset + vertex_count * 12 > len(data)
        or face_offset + face_count * 12 > len(data)
        or old_aabb_offset + old_aabb_count * 44 > len(data)
        or old_adjacency_offset + adjacency_count * 12 > len(data)
        or old_edge_offset + edge_count * 8 > len(data)
        or old_perimeter_offset + perimeter_count * 4 > len(data)
    ):
        return data

    vertices = [struct.unpack_from("<3f", data, vertex_offset + index * 12) for index in range(vertex_count)]
    faces = [struct.unpack_from("<III", data, face_offset + index * 12) for index in range(face_count)]
    face_rows: list[tuple[int, tuple[tuple[float, float, float], ...], tuple[float, float, float]]] = []
    for face_index, face in enumerate(faces):
        if any(vertex_index >= vertex_count for vertex_index in face):
            return data
        corners = tuple(vertices[vertex_index] for vertex_index in face)
        centre = tuple(sum(corner[axis] for corner in corners) / 3.0 for axis in range(3))
        face_rows.append((face_index, corners, centre))

    nodes: list[dict[str, Any]] = []

    def _build(rows: list[tuple[int, tuple[tuple[float, float, float], ...], tuple[float, float, float]]], depth: int = 0) -> int:
        if not rows or depth > 128:
            raise ValueError("Generated WOK AABB tree exceeded its safe recursion contract.")
        bounds_min = tuple(min(corner[axis] for _index, corners, _centre in rows for corner in corners) for axis in range(3))
        bounds_max = tuple(max(corner[axis] for _index, corners, _centre in rows for corner in corners) for axis in range(3))
        node_index = len(nodes)
        nodes.append({})
        if len(rows) == 1:
            nodes[node_index] = {
                "min": bounds_min,
                "max": bounds_max,
                "face": rows[0][0],
                "plane": 0,
                "left": -1,
                "right": -1,
            }
            return node_index

        extents = tuple(bounds_max[axis] - bounds_min[axis] for axis in range(3))
        axis = max(range(3), key=lambda value: (extents[value], -value))
        left: list[Any] = []
        right: list[Any] = []
        actual_axis = axis
        for attempt in range(3):
            actual_axis = (axis + attempt) % 3
            split = sum(row[2][actual_axis] for row in rows) / len(rows)
            left = [row for row in rows if row[2][actual_axis] < split]
            right = [row for row in rows if row[2][actual_axis] >= split]
            if left and right:
                break
        if not left or not right:
            # Equal-centroid and otherwise unsplittable input: stable median
            # partition retains every face and keeps tree depth logarithmic.
            ordered = sorted(
                rows,
                key=lambda row: (
                    row[2][actual_axis],
                    row[2][(actual_axis + 1) % 3],
                    row[2][(actual_axis + 2) % 3],
                    row[0],
                ),
            )
            midpoint = max(1, len(ordered) // 2)
            left, right = ordered[:midpoint], ordered[midpoint:]
        left_index = _build(left, depth + 1)
        right_index = _build(right, depth + 1)
        nodes[node_index] = {
            "min": bounds_min,
            "max": bounds_max,
            "face": -1,
            "plane": (1, 2, 4)[actual_axis],
            "left": left_index,
            "right": right_index,
        }
        return node_index

    root = _build(face_rows)
    aabb_data = bytearray()
    for node in nodes:
        aabb_data += struct.pack("<6f", *node["min"], *node["max"])
        aabb_data += struct.pack(
            "<IIIII",
            int(node["face"]) & 0xFFFFFFFF,
            4,
            int(node["plane"]),
            int(node["left"]) & 0xFFFFFFFF,
            int(node["right"]) & 0xFFFFFFFF,
        )

    adjacency_data = data[old_adjacency_offset : old_adjacency_offset + adjacency_count * 12]
    edge_data = data[old_edge_offset : old_edge_offset + edge_count * 8]
    perimeter_data = data[old_perimeter_offset : old_perimeter_offset + perimeter_count * 4]
    rebuilt = bytearray(data[:old_aabb_offset])
    rebuilt += aabb_data
    adjacency_offset = len(rebuilt)
    rebuilt += adjacency_data
    edge_offset = len(rebuilt)
    rebuilt += edge_data
    perimeter_offset = len(rebuilt)
    rebuilt += perimeter_data
    struct.pack_into("<III", rebuilt, 100, len(nodes), old_aabb_offset, root)
    struct.pack_into("<II", rebuilt, 112, adjacency_count, adjacency_offset)
    struct.pack_into("<II", rebuilt, 120, edge_count, edge_offset)
    struct.pack_into("<II", rebuilt, 128, perimeter_count, perimeter_offset)
    return bytes(rebuilt)


def _patch_bwm_perimeters(data: bytes, *, source_raw: Optional[bytes] = None) -> bytes:
    """Repair index-topology adjacency and emit every perimeter loop.

    A KOTOR area walkmesh needs perimeter records grouping its boundary edges
    into closed loops; without them the engine treats the walkable region as
    undefined and the player cannot move (perim=0).  PyKotor can omit boundary
    edges or emit touching/multiple loops out of order.  Rebuild the boundary
    from the serialized walkable triangles, trace every closed directed loop,
    preserve transition indices, then replace the edge/perimeter tail.

    Vertex *indices* are authoritative here.  Vanilla WOKs deliberately retain
    duplicate-coordinate vertices at some collision seams.  PyKotor's
    adjacency builder compares ``Vector3`` values, which welds those distinct
    indices and can serialize an adjacency that contradicts the perimeter
    table.  Patch the adjacency rows from the actual serialized face indices
    before rebuilding the boundary.  A walkable edge with more than two raw
    owners is not representable by Odyssey's one-neighbour adjacency row, so
    refuse to serialize it instead of choosing an arbitrary neighbour.
    """

    data = _rebuild_bwm_aabb_tree(data)
    if len(data) < 136:
        return data
    fc, fo = struct.unpack_from("<II", data, 80)
    walkable_count, adjacency_offset = struct.unpack_from("<II", data, 112)
    ec, eo = struct.unpack_from("<II", data, 120)
    if not fc or not walkable_count:
        return data  # nothing walkable to trace
    if (
        fo + fc * 12 > len(data)
        or adjacency_offset + walkable_count * 12 > len(data)
        or eo + ec * 8 > len(data)
        or walkable_count > fc
    ):
        return data
    faces = [struct.unpack_from("<III", data, fo + 12 * i) for i in range(fc)]

    # Rebuild adjacency strictly from vertex indices.  Using coordinates here
    # destroys intentional vanilla seams made from coincident-but-distinct
    # vertices and disagrees with the perimeter table derived below.
    indexed_owners: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
    for face_index in range(walkable_count):
        triangle = faces[face_index]
        for local_edge in range(3):
            key = tuple(sorted((triangle[local_edge], triangle[(local_edge + 1) % 3])))
            indexed_owners.setdefault(key, []).append((face_index, local_edge))
    indexed_adjacency = [[-1, -1, -1] for _ in range(walkable_count)]
    for edge, owners in indexed_owners.items():
        if len(owners) > 2:
            raise ValueError(
                "Walkable WOK edge "
                f"{edge[0]}-{edge[1]} has {len(owners)} face owners; "
                "Odyssey adjacency supports at most two."
            )
        if len(owners) == 2:
            (face_a, edge_a), (face_b, edge_b) = owners
            indexed_adjacency[face_a][edge_a] = face_b * 3 + edge_b
            indexed_adjacency[face_b][edge_b] = face_a * 3 + edge_a

    existing_rows = [struct.unpack_from("<ii", data, eo + 8 * i) for i in range(ec)]
    transition_by_edge: Dict[int, int] = {}
    for edge_id, transition in existing_rows:
        if transition != -1 or edge_id not in transition_by_edge:
            transition_by_edge[edge_id] = transition

    edge_owners: Dict[Tuple[int, int], List[Tuple[int, int, int]]] = {}
    for face_index in range(walkable_count):
        triangle = faces[face_index]
        for local_edge in range(3):
            start = triangle[local_edge]
            end = triangle[(local_edge + 1) % 3]
            if start == end:
                # Imported retail data contains a tiny number of degenerate
                # legacy faces.  They are not usable boundary topology and new
                # authoring rejects them before serialization.
                continue
            key = tuple(sorted((start, end)))
            edge_owners.setdefault(key, []).append((face_index * 3 + local_edge, start, end))
    for edge, rows in edge_owners.items():
        if len(rows) == 2 and (rows[0][1] != rows[1][2] or rows[0][2] != rows[1][1]):
            raise ValueError(
                "Walkable WOK edge "
                f"{edge[0]}-{edge[1]} has same-direction owners; "
                "adjacent floor triangles must have consistent winding."
            )
    boundary = [rows[0] for rows in edge_owners.values() if len(rows) == 1]
    if not boundary:
        raise ValueError("Walkable WOK has no traceable raw-index boundary.")

    boundary_by_id = {row[0]: row for row in boundary}

    def _next_boundary(edge_id: int) -> int:
        """Follow one topology fan to its next boundary half-edge.

        Choosing an arbitrary outgoing edge by vertex fails where separate
        islands or a hole touch at one vertex.  Crossing explicit face
        adjacency keeps those fans independent and deterministically traces
        every loop.
        """

        face_index, local_edge = divmod(edge_id, 3)
        candidate_edge = (local_edge + 1) % 3
        visited_internal: set[int] = set()
        while indexed_adjacency[face_index][candidate_edge] != -1:
            candidate_id = face_index * 3 + candidate_edge
            if candidate_id in visited_internal:
                raise ValueError("Walkable WOK boundary traversal cycled through internal adjacency.")
            visited_internal.add(candidate_id)
            adjacent_id = indexed_adjacency[face_index][candidate_edge]
            face_index, shared_edge = divmod(adjacent_id, 3)
            candidate_edge = (shared_edge + 1) % 3
        return face_index * 3 + candidate_edge

    unvisited = set(boundary_by_id)
    ordered: List[Tuple[int, int, int]] = []
    perimeters: List[int] = []
    while unvisited:
        first_id = min(unvisited)
        current_id = first_id
        loop_seen: set[int] = set()
        while True:
            if current_id in loop_seen:
                raise ValueError("Walkable WOK boundary traversal repeated an edge before closing.")
            if current_id not in unvisited or current_id not in boundary_by_id:
                raise ValueError("Walkable WOK boundary traversal reached a missing or previously consumed edge.")
            loop_seen.add(current_id)
            unvisited.remove(current_id)
            ordered.append(boundary_by_id[current_id])
            next_id = _next_boundary(current_id)
            if next_id == first_id:
                perimeters.append(len(ordered))
                break
            current_id = next_id

    # When this WOK came directly from a retail/imported binary and its
    # directed boundary IDs are unchanged, retain the source loop grouping.
    # Vanilla sometimes splits or chains cycles at pinched vertices differently
    # from the canonical topology-fan trace above.  Both are closed, but exact
    # preservation is the safer import/export fidelity contract.
    if source_raw is not None and len(source_raw) >= 136:
        try:
            source_face_count = struct.unpack_from("<I", source_raw, 80)[0]
            source_adjacency_count = struct.unpack_from("<I", source_raw, 112)[0]
            source_edge_count, source_edge_offset = struct.unpack_from("<II", source_raw, 120)
            source_perimeter_count, source_perimeter_offset = struct.unpack_from("<II", source_raw, 128)
            source_in_bounds = bool(
                source_face_count == fc
                and source_adjacency_count == walkable_count
                and source_edge_offset + source_edge_count * 8 <= len(source_raw)
                and source_perimeter_offset + source_perimeter_count * 4 <= len(source_raw)
            )
            if source_in_bounds:
                source_edge_ids = [
                    struct.unpack_from("<I", source_raw, source_edge_offset + index * 8)[0]
                    for index in range(source_edge_count)
                ]
                source_endpoints = [
                    struct.unpack_from("<I", source_raw, source_perimeter_offset + index * 4)[0]
                    for index in range(source_perimeter_count)
                ]
                boundary_ids_now = set(boundary_by_id)
                endpoints_valid = bool(
                    source_endpoints
                    and source_endpoints[-1] == len(source_edge_ids)
                    and all(
                        endpoint > (source_endpoints[index - 1] if index else 0)
                        for index, endpoint in enumerate(source_endpoints)
                    )
                )
                source_order_valid = bool(
                    len(source_edge_ids) == len(boundary_ids_now)
                    and len(set(source_edge_ids)) == len(source_edge_ids)
                    and set(source_edge_ids) == boundary_ids_now
                    and endpoints_valid
                )
                if source_order_valid:
                    previous = 0
                    for endpoint in source_endpoints:
                        loop = [boundary_by_id[edge_id] for edge_id in source_edge_ids[previous:endpoint]]
                        if not loop or any(
                            loop[index][2] != loop[(index + 1) % len(loop)][1]
                            for index in range(len(loop))
                        ):
                            source_order_valid = False
                            break
                        previous = endpoint
                if source_order_valid:
                    ordered = [boundary_by_id[edge_id] for edge_id in source_edge_ids]
                    perimeters = source_endpoints
        except (IndexError, KeyError, struct.error, TypeError, ValueError):
            pass

    boundary_ids = {row[0] for row in ordered}
    orphan_transitions = [
        edge_id
        for edge_id, transition in existing_rows
        if transition != -1 and edge_id not in boundary_ids
    ]
    if orphan_transitions:
        raise ValueError(
            f"Walkable WOK has {len(orphan_transitions)} transition edge(s) outside its perimeter boundary."
        )
    edge_rows = [(edge_id, transition_by_edge.get(edge_id, -1)) for edge_id, _start, _end in ordered]

    buf = bytearray(data[:eo])
    for face_index, row in enumerate(indexed_adjacency):
        struct.pack_into("<iii", buf, adjacency_offset + face_index * 12, *row)
    for edge_id, transition in edge_rows:
        buf += struct.pack("<ii", edge_id, transition)
    perim_off = len(buf)
    for value in perimeters:
        buf += struct.pack("<I", value)
    struct.pack_into("<II", buf, 120, len(edge_rows), eo)
    struct.pack_into("<II", buf, 128, len(perimeters), perim_off)
    return bytes(buf)


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
