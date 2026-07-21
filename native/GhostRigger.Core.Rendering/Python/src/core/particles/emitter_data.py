"""Canonical KOTOR emitter controller table and emitter definition model.

The controller-type numbering below is the K1/K2 binary emitter numbering used
by KotorBlender/reone/mdlops and was verified empirically against retail data
(K1 ``plc_starmap``): ``Sun_gas`` decodes to birthrate=50, velocity=0.07,
spread=360, lifeexp=2, colorstart/mid/end=(1.0, 0.68, 0.0), alphastart=1,
alphamid=1, alphaend=0, sizestart/mid=0.15, sizeend=0.05 — a shrinking,
fading orange gas fountain, exactly what the in-game starmap shows.

Do NOT use the xoreos ``model_kotor.cpp`` emitter numbering here (for example
AlphaMid=464); it diverges from retail K1/K2 binaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntFlag
from typing import Any, Dict, List, Optional, Sequence, Tuple


# ── Emitter controller types (binary MDL node controller ids) ────────────────
# id → (canonical ASCII name, column count)
EMITTER_CONTROLLER_TYPES: Dict[int, Tuple[str, int]] = {
    8:   ("position", 3),
    20:  ("orientation", 4),
    80:  ("alphaend", 1),
    84:  ("alphastart", 1),
    88:  ("birthrate", 1),
    92:  ("bounce_co", 1),
    96:  ("combinetime", 1),
    100: ("drag", 1),
    104: ("fps", 1),
    108: ("frameend", 1),
    112: ("framestart", 1),
    116: ("grav", 1),
    120: ("lifeexp", 1),
    124: ("mass", 1),
    128: ("p2p_bezier2", 1),
    132: ("p2p_bezier3", 1),
    136: ("particlerot", 1),
    140: ("randvel", 1),
    144: ("sizestart", 1),
    148: ("sizeend", 1),
    152: ("sizestart_y", 1),
    156: ("sizeend_y", 1),
    160: ("spread", 1),
    164: ("threshold", 1),
    168: ("velocity", 1),
    172: ("xsize", 1),
    176: ("ysize", 1),
    180: ("blurlength", 1),
    184: ("lightningdelay", 1),
    188: ("lightningradius", 1),
    192: ("lightningscale", 1),
    196: ("lightningsubdiv", 1),
    200: ("lightningzigzag", 1),
    216: ("alphamid", 1),
    220: ("percentstart", 1),
    224: ("percentmid", 1),
    228: ("percentend", 1),
    232: ("sizemid", 1),
    236: ("sizemid_y", 1),
    240: ("randombirthrate", 1),
    252: ("targetsize", 1),
    256: ("numcontrolpts", 1),
    260: ("controlptradius", 1),
    264: ("controlptdelay", 1),
    268: ("tangentspread", 1),
    272: ("tangentlength", 1),
    284: ("colormid", 3),
    380: ("colorend", 3),
    392: ("colorstart", 3),
    502: ("detonate", 1),
}

EMITTER_CONTROLLER_ID_BY_NAME: Dict[str, int] = {
    name: ctrl_id for ctrl_id, (name, _cols) in EMITTER_CONTROLLER_TYPES.items()
}

# Channels the simulation/editor treat as colors (3 columns).
COLOR_CHANNELS = ("colorstart", "colormid", "colorend")

# Update / render / blend string vocabularies as stored in binary MDL headers.
UPDATE_MODES = ("Fountain", "Single", "Explosion", "Lightning")
RENDER_MODES = (
    "Normal",
    "Linked",
    "Billboard_to_Local_Z",
    "Billboard_to_World_Z",
    "Aligned_to_World_Z",
    "Aligned_to_Particle_Dir",
    "Motion_Blur",
)
BLEND_MODES = ("Normal", "Punch-Through", "Lighten")


class EmitterFlags(IntFlag):
    """Emitter header flag bits (Odyssey binary MDL emitter header)."""

    P2P = 0x0001
    P2P_SEL = 0x0002
    AFFECTED_BY_WIND = 0x0004
    TINTED = 0x0008
    BOUNCE = 0x0010
    RANDOM = 0x0020
    INHERIT = 0x0040
    INHERIT_VEL = 0x0080
    INHERIT_LOCAL = 0x0100
    SPLAT = 0x0200
    INHERIT_PART = 0x0400
    DEPTH_TEXTURE = 0x0800


# Channel rows: list of (time, (v0, v1, ...)) keyframes sorted by time.
ChannelRows = List[Tuple[float, Tuple[float, ...]]]

# Editor-facing default values for every scalar/color channel.
CHANNEL_DEFAULTS: Dict[str, Tuple[float, ...]] = {
    "alphaend": (0.0,),
    "alphastart": (1.0,),
    "alphamid": (0.5,),
    "birthrate": (0.0,),
    "randombirthrate": (0.0,),
    "bounce_co": (0.0,),
    "combinetime": (0.0,),
    "drag": (0.0,),
    "fps": (0.0,),
    "frameend": (0.0,),
    "framestart": (0.0,),
    "grav": (0.0,),
    "lifeexp": (1.0,),
    "mass": (0.0,),
    "p2p_bezier2": (0.0,),
    "p2p_bezier3": (0.0,),
    "particlerot": (0.0,),
    "randvel": (0.0,),
    "sizestart": (1.0,),
    "sizeend": (1.0,),
    "sizemid": (1.0,),
    "sizestart_y": (0.0,),
    "sizeend_y": (0.0,),
    "sizemid_y": (0.0,),
    "spread": (0.0,),
    "threshold": (0.0,),
    "velocity": (0.0,),
    "xsize": (0.0,),
    "ysize": (0.0,),
    "blurlength": (0.0,),
    "lightningdelay": (0.0,),
    "lightningradius": (0.0,),
    "lightningscale": (0.0,),
    "lightningsubdiv": (0.0,),
    "lightningzigzag": (0.0,),
    "percentstart": (0.0,),
    "percentmid": (0.5,),
    "percentend": (1.0,),
    "targetsize": (0.0,),
    "numcontrolpts": (0.0,),
    "controlptradius": (0.0,),
    "controlptdelay": (0.0,),
    "tangentspread": (0.0,),
    "tangentlength": (0.0,),
    "colorstart": (1.0, 1.0, 1.0),
    "colormid": (1.0, 1.0, 1.0),
    "colorend": (1.0, 1.0, 1.0),
    "detonate": (0.0,),
}


def sample_channel(rows: Optional[ChannelRows], t: float,
                   default: Tuple[float, ...] = (0.0,)) -> Tuple[float, ...]:
    """Sample keyframe rows at time *t* with linear interpolation and clamping."""
    if not rows:
        return default
    if len(rows) == 1 or t <= rows[0][0]:
        return rows[0][1]
    if t >= rows[-1][0]:
        return rows[-1][1]
    for index in range(1, len(rows)):
        t1, v1 = rows[index]
        if t <= t1:
            t0, v0 = rows[index - 1]
            span = max(1e-9, t1 - t0)
            f = (t - t0) / span
            n = min(len(v0), len(v1))
            return tuple(v0[k] + (v1[k] - v0[k]) * f for k in range(n))
    return rows[-1][1]


def _channel_rows_from_controller(ctrl: Dict[str, Any]) -> ChannelRows:
    times = ctrl.get("times") or []
    values = ctrl.get("values") or []
    rows: ChannelRows = []
    for index, time_key in enumerate(times):
        if index >= len(values):
            break
        row = values[index]
        try:
            rows.append((float(time_key), tuple(float(v) for v in row)))
        except (TypeError, ValueError):
            continue
    rows.sort(key=lambda item: item[0])
    return rows


def controllers_to_channels(controllers: Sequence[Dict[str, Any]]) -> Dict[str, ChannelRows]:
    """Decode raw emitter node controllers into named channels.

    Position/orientation stay out of the channel dict — they belong to the
    node transform, not the particle parameter set.
    """
    channels: Dict[str, ChannelRows] = {}
    for ctrl in controllers or []:
        try:
            ctrl_id = int(ctrl.get("type", -1))
        except (TypeError, ValueError):
            continue
        entry = EMITTER_CONTROLLER_TYPES.get(ctrl_id)
        if entry is None or ctrl_id in (8, 20):
            continue
        name, cols = entry
        rows = _channel_rows_from_controller(ctrl)
        if not rows:
            continue
        channels[name] = [(t, v[:cols] if len(v) >= cols else v) for t, v in rows]
    return channels


@dataclass
class ForceField:
    """A Ghost Studio point force acting on an emitter's live particles.

    This is NOT part of the KOTOR binary emitter model; it is a Ghost Studio
    authoring extension inspired by the GPU gravity wells in
    conanwu777/particle_system.  It lets an emitter produce swirling, orbiting,
    and imploding motion that the stock birthrate/velocity/gravity controllers
    cannot express.  ``position`` is emitter-relative and ``strength`` follows
    an inverse-distance law (``a += strength * disp / sqrt(|disp|^2 + eps)``).
    """

    mode: str = "attract"                                 # attract | repel | vortex
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    strength: float = 1.0
    radius: float = 0.0                                   # 0 = unbounded influence
    axis: Tuple[float, float, float] = (0.0, 0.0, 1.0)    # vortex swirl axis

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": str(self.mode),
            "position": [float(v) for v in self.position],
            "strength": float(self.strength),
            "radius": float(self.radius),
            "axis": [float(v) for v in self.axis],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForceField":
        def _vec3(raw: Any, fallback: Tuple[float, float, float]) -> Tuple[float, float, float]:
            try:
                return (float(raw[0]), float(raw[1]), float(raw[2]))
            except (TypeError, ValueError, IndexError):
                return fallback

        mode = str((data or {}).get("mode", "attract") or "attract").lower()
        if mode not in ("attract", "repel", "vortex"):
            mode = "attract"
        return cls(
            mode=mode,
            position=_vec3((data or {}).get("position"), (0.0, 0.0, 0.0)),
            strength=float((data or {}).get("strength", 1.0) or 0.0),
            radius=max(0.0, float((data or {}).get("radius", 0.0) or 0.0)),
            axis=_vec3((data or {}).get("axis"), (0.0, 0.0, 1.0)),
        )


def _force_fields_from_raw(raw: Any) -> List[ForceField]:
    fields: List[ForceField] = []
    for item in raw or []:
        try:
            fields.append(ForceField.from_dict(item))
        except Exception:
            continue
    return fields


@dataclass
class EmitterDefinition:
    """One emitter node's complete authorable parameter set."""

    name: str = "emitter"
    update: str = "Fountain"
    render: str = "Normal"
    blend: str = "Normal"
    texture: str = ""
    chunk_name: str = ""
    depth_texture: str = ""
    two_sided_texture: int = 0
    loop: int = 0
    render_order: int = 0
    frame_blending: int = 0
    grid_x: int = 1
    grid_y: int = 1
    spawn_type: int = 0
    dead_space: float = 0.0
    blast_radius: float = 0.0
    blast_length: float = 0.0
    branch_count: int = 0
    control_point_smoothing: int = 0
    flags: int = 0
    channels: Dict[str, ChannelRows] = field(default_factory=dict)
    # Ghost Studio authoring extensions (not part of the KOTOR binary model).
    force_fields: List[ForceField] = field(default_factory=list)
    hue_cycle_speed: float = 0.0

    # ── Channel access ───────────────────────────────────────────────────────
    def value(self, channel: str, t: float = 0.0) -> float:
        default = CHANNEL_DEFAULTS.get(channel, (0.0,))
        return float(sample_channel(self.channels.get(channel), t, default)[0])

    def color(self, channel: str, t: float = 0.0) -> Tuple[float, float, float]:
        default = CHANNEL_DEFAULTS.get(channel, (1.0, 1.0, 1.0))
        sampled = sample_channel(self.channels.get(channel), t, default)
        if len(sampled) < 3:
            sampled = tuple(sampled) + (1.0,) * (3 - len(sampled))
        return (float(sampled[0]), float(sampled[1]), float(sampled[2]))

    def set_value(self, channel: str, value: float) -> None:
        self.channels[channel] = [(0.0, (float(value),))]

    def set_color(self, channel: str, rgb: Sequence[float]) -> None:
        self.channels[channel] = [(0.0, (float(rgb[0]), float(rgb[1]), float(rgb[2])))]

    @property
    def flag_bits(self) -> EmitterFlags:
        return EmitterFlags(int(self.flags))

    # ── Node round-trips ─────────────────────────────────────────────────────
    @classmethod
    def from_node(cls, node: Any) -> "EmitterDefinition":
        """Build a definition from a GhostRigger ``ModelNode`` emitter node."""
        params = dict(getattr(node, "emitter_params", {}) or {})
        defn = cls(
            name=str(getattr(node, "name", "") or "emitter"),
            update=str(params.get("update", "") or "Fountain"),
            render=str(params.get("emitter_render", "") or "Normal"),
            blend=str(params.get("blend", "") or "Normal"),
            texture=str(params.get("texture", "") or ""),
            chunk_name=str(params.get("chunkname", "") or ""),
            depth_texture=str(params.get("depth_texture_name", "") or ""),
            two_sided_texture=int(params.get("twosidedtex", 0) or 0),
            loop=int(params.get("loop", 0) or 0),
            render_order=int(params.get("renderorder", 0) or 0),
            frame_blending=int(params.get("frameblending", 0) or 0),
            grid_x=max(1, int(params.get("xgrid", 1) or 1)),
            grid_y=max(1, int(params.get("ygrid", 1) or 1)),
            spawn_type=int(params.get("spawntype", 0) or 0),
            dead_space=float(params.get("deadspace", 0.0) or 0.0),
            blast_radius=float(params.get("blastradius", 0.0) or 0.0),
            blast_length=float(params.get("blastlength", 0.0) or 0.0),
            branch_count=int(params.get("numbranches", 0) or 0),
            control_point_smoothing=int(params.get("controlptsmoothing", 0) or 0),
            flags=int(params.get("flags", 0) or 0),
        )
        defn.channels = controllers_to_channels(getattr(node, "controllers", None) or [])
        defn.force_fields = _force_fields_from_raw(params.get("gr_force_fields"))
        defn.hue_cycle_speed = float(params.get("gr_hue_cycle_speed", 0.0) or 0.0)
        return defn

    def header_params(self) -> Dict[str, Any]:
        """Return the emitter header dict in ``ModelNode.emitter_params`` layout.

        Ghost Studio's non-KOTOR extensions (``gr_force_fields``,
        ``gr_hue_cycle_speed``) are only emitted when set, so stock emitters
        keep a byte-identical header and the MDL writer (which reads the fixed
        Odyssey fields) simply ignores the extra keys.
        """
        params: Dict[str, Any] = {
            "deadspace": float(self.dead_space),
            "blastradius": float(self.blast_radius),
            "blastlength": float(self.blast_length),
            "numbranches": int(self.branch_count),
            "controlptsmoothing": int(self.control_point_smoothing),
            "xgrid": int(self.grid_x),
            "ygrid": int(self.grid_y),
            "spawntype": int(self.spawn_type),
            "update": str(self.update),
            "emitter_render": str(self.render),
            "blend": str(self.blend),
            "texture": str(self.texture),
            "chunkname": str(self.chunk_name),
            "twosidedtex": int(self.two_sided_texture),
            "loop": int(self.loop),
            "renderorder": int(self.render_order),
            "frameblending": int(self.frame_blending),
            "depth_texture_name": str(self.depth_texture),
            "flags": int(self.flags),
        }
        if self.force_fields:
            params["gr_force_fields"] = [f.to_dict() for f in self.force_fields]
        if self.hue_cycle_speed:
            params["gr_hue_cycle_speed"] = float(self.hue_cycle_speed)
        return params

    def apply_to_node(self, node: Any) -> None:
        """Write header + channels back into a ``ModelNode`` emitter node.

        Preserves round-trip metadata keys (``unknown1``) already present in
        ``emitter_params`` and the node's position/orientation controllers.
        """
        params = dict(getattr(node, "emitter_params", {}) or {})
        params.update(self.header_params())
        node.emitter_params = params

        keep = [
            ctrl for ctrl in (getattr(node, "controllers", None) or [])
            if int(ctrl.get("type", -1)) in (8, 20)
            or int(ctrl.get("type", -1)) not in EMITTER_CONTROLLER_TYPES
        ]
        for name, rows in self.channels.items():
            ctrl_id = EMITTER_CONTROLLER_ID_BY_NAME.get(name)
            if ctrl_id is None or not rows:
                continue
            cols = EMITTER_CONTROLLER_TYPES[ctrl_id][1]
            keep.append({
                "type": ctrl_id,
                "name": name,
                "columns": cols,
                "times": [float(t) for t, _v in rows],
                "values": [list(v[:cols]) for _t, v in rows],
            })
        node.controllers = keep

    # ── Dict round-trips (templates / JSON cache) ────────────────────────────
    def to_dict(self) -> Dict[str, Any]:
        payload = self.header_params()
        payload["name"] = self.name
        payload["channels"] = {
            name: [[float(t), [float(v) for v in row]] for t, row in rows]
            for name, rows in self.channels.items()
        }
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmitterDefinition":
        defn = cls(
            name=str(data.get("name", "") or "emitter"),
            update=str(data.get("update", "") or "Fountain"),
            render=str(data.get("emitter_render", data.get("render", "")) or "Normal"),
            blend=str(data.get("blend", "") or "Normal"),
            texture=str(data.get("texture", "") or ""),
            chunk_name=str(data.get("chunkname", data.get("chunk_name", "")) or ""),
            depth_texture=str(data.get("depth_texture_name", "") or ""),
            two_sided_texture=int(data.get("twosidedtex", 0) or 0),
            loop=int(data.get("loop", 0) or 0),
            render_order=int(data.get("renderorder", 0) or 0),
            frame_blending=int(data.get("frameblending", 0) or 0),
            grid_x=max(1, int(data.get("xgrid", 1) or 1)),
            grid_y=max(1, int(data.get("ygrid", 1) or 1)),
            spawn_type=int(data.get("spawntype", 0) or 0),
            dead_space=float(data.get("deadspace", 0.0) or 0.0),
            blast_radius=float(data.get("blastradius", 0.0) or 0.0),
            blast_length=float(data.get("blastlength", 0.0) or 0.0),
            branch_count=int(data.get("numbranches", 0) or 0),
            control_point_smoothing=int(data.get("controlptsmoothing", 0) or 0),
            flags=int(data.get("flags", 0) or 0),
        )
        channels: Dict[str, ChannelRows] = {}
        for name, rows in (data.get("channels") or {}).items():
            decoded: ChannelRows = []
            for row in rows:
                try:
                    decoded.append((float(row[0]), tuple(float(v) for v in row[1])))
                except (TypeError, ValueError, IndexError):
                    continue
            if decoded:
                channels[str(name)] = decoded
        defn.channels = channels
        defn.force_fields = _force_fields_from_raw(data.get("gr_force_fields"))
        defn.hue_cycle_speed = float(data.get("gr_hue_cycle_speed", 0.0) or 0.0)
        return defn


def emitter_nodes(model: Any) -> List[Any]:
    """Return the emitter nodes of a ``KotorModel`` (empty when none)."""
    nodes_fn = getattr(model, "all_nodes", None)
    nodes = list(nodes_fn()) if callable(nodes_fn) else list(getattr(model, "nodes", []) or [])
    return [node for node in nodes if bool(getattr(node, "is_emitter", False))]


def animation_channels_for_node(animation: Any, node_name: str) -> Dict[str, ChannelRows]:
    """Decode the emitter channels an animation block keys on *node_name*."""
    if animation is None:
        return {}
    key = str(node_name or "").lower()
    for anim_node in getattr(animation, "nodes", None) or []:
        if str(getattr(anim_node, "name", "") or "").lower() == key:
            return controllers_to_channels(getattr(anim_node, "controllers", None) or [])
    return {}
