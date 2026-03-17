"""
KotOR Animation Engine
======================
Handles animation playback, interpolation, export (BVH / FBX-ASCII / JSON),
and import (JSON / BVH) for KotOR MDL models.

Animation data pipeline:
  Binary MDL  →  MDLBinaryParser  →  KotorModel.animations  →  AnimationEngine
                                                              ↕
                                               viewport pose evaluation
"""

import math
import json
import logging
import os
import struct
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any

from .model_data import (
    Animation, AnimEvent, ModelNode, KotorModel,
    _quat_mul, _quat_rotate, _quat_normalize_bind
)

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
#  Interpolation helpers
# ─────────────────────────────────────────────────────────────────

def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _lerp3(a: Tuple, b: Tuple, t: float) -> Tuple:
    return (
        _lerp(a[0], b[0], t),
        _lerp(a[1], b[1], t),
        _lerp(a[2], b[2], t),
    )


def _slerp(q1: List[float], q2: List[float], t: float) -> List[float]:
    """Spherical linear interpolation between two quaternions [x,y,z,w]."""
    x1, y1, z1, w1 = q1
    x2, y2, z2, w2 = q2
    dot = x1*x2 + y1*y2 + z1*z2 + w1*w2
    # Ensure shortest path
    if dot < 0:
        x2, y2, z2, w2 = -x2, -y2, -z2, -w2
        dot = -dot
    if dot > 0.9995:
        # Linear interpolation for nearly identical quats
        rx = x1 + t*(x2-x1)
        ry = y1 + t*(y2-y1)
        rz = z1 + t*(z2-z1)
        rw = w1 + t*(w2-w1)
    else:
        theta_0 = math.acos(dot)
        theta = theta_0 * t
        sin_theta = math.sin(theta)
        sin_theta_0 = math.sin(theta_0)
        s1 = math.cos(theta) - dot * sin_theta / sin_theta_0
        s2 = sin_theta / sin_theta_0
        rx = s1*x1 + s2*x2
        ry = s1*y1 + s2*y2
        rz = s1*z1 + s2*z2
        rw = s1*w1 + s2*w2
    # Normalize
    mag = math.sqrt(rx*rx + ry*ry + rz*rz + rw*rw)
    if mag > 1e-9:
        rx /= mag; ry /= mag; rz /= mag; rw /= mag
    return [rx, ry, rz, rw]


def _is_finite_vec(v) -> bool:
    """Return True if all elements of v are finite (not NaN/Inf)."""
    return all(math.isfinite(x) for x in v)


def _interp_channel(times: List[float], values: List[List[float]],
                    t: float) -> Optional[List[float]]:
    """
    Interpolate a controller channel at time t.
    Returns the interpolated value list, or None if no keys.

    NaN/Inf safety: skips keyframe pairs that contain non-finite values
    so that corrupt data in bezier-spline tail regions does not propagate.
    """
    if not times or not values:
        return None

    # Find last valid keyframe at or before t
    # Walk forward/backward to skip NaN-contaminated entries
    def safe_val(idx):
        v = values[idx]
        return v if _is_finite_vec(v) else None

    if t <= times[0]:
        v = safe_val(0)
        return list(v) if v else None
    if t >= times[-1]:
        # Walk backward to find last finite keyframe
        for i in range(len(times) - 1, -1, -1):
            v = safe_val(i)
            if v is not None:
                return list(v)
        return None

    # Binary search for bracketing keys
    lo, hi = 0, len(times) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if times[mid] <= t:
            lo = mid
        else:
            hi = mid

    # Expand lo/hi to valid (finite) values
    lo2 = lo
    while lo2 >= 0 and safe_val(lo2) is None:
        lo2 -= 1
    hi2 = hi
    while hi2 < len(times) and safe_val(hi2) is None:
        hi2 += 1

    if lo2 < 0 and hi2 >= len(times):
        return None
    if lo2 < 0:
        return list(safe_val(hi2))
    if hi2 >= len(times):
        return list(safe_val(lo2))

    tf = (t - times[lo2]) / max(1e-9, times[hi2] - times[lo2])
    v0, v1 = values[lo2], values[hi2]
    if len(v0) == 4:   # quaternion – slerp
        return _slerp(v0, v1, tf)
    elif len(v0) == 3:
        return list(_lerp3(v0, v1, tf))
    else:
        return [_lerp(v0[k], v1[k], tf) for k in range(min(len(v0), len(v1)))]


# ─────────────────────────────────────────────────────────────────
#  Pose snapshot
# ─────────────────────────────────────────────────────────────────

@dataclass
class NodePose:
    """Animated pose for a single node at a given time."""
    name:     str
    position: Tuple[float, float, float]        = (0.0, 0.0, 0.0)
    rotation: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)  # xyzw
    scale:    float = 1.0
    # Per-node material animation (CTRL_MESH_ALPHA=132, CTRL_MESH_SELFILLUMCOLOR=100)
    alpha:      Optional[float]                     = None  # None = use bind-pose value
    selfillum:  Optional[Tuple[float,float,float]]  = None  # None = use bind-pose value


@dataclass
class AnimPose:
    """Complete model pose at a given time step."""
    time:   float = 0.0
    nodes:  Dict[str, NodePose] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────
#  Animation Engine
# ─────────────────────────────────────────────────────────────────

class AnimationEngine:
    """
    Manages animation playback for a KotorModel.

    Usage:
        engine = AnimationEngine(model)
        engine.play('cwalk')
        pose   = engine.evaluate(0.5)   # pose at t=0.5s
        engine.stop()
    """

    # Controller type IDs  (verified against KotorBlender types.py and xoreos)
    CTRL_POSITION       = 8
    CTRL_ORIENTATION    = 20
    CTRL_SCALE          = 36
    CTRL_SELFILLUMCOLOR = 100   # CTRL_MESH_SELFILLUMCOLOR: r,g,b (3 floats)
    CTRL_ALPHA_XOREOS   = 128   # xoreos CTRL_ALPHA = 128 (some tools use this)
    CTRL_ALPHA          = 132   # CTRL_MESH_ALPHA = 132 (KotorBlender convention)

    def __init__(self, model: KotorModel):
        self.model    = model
        self._current_anim: Optional[Animation] = None
        self._loop    = True
        self._playing = False
        self._time    = 0.0
        # Build lookup: name → base-pose node
        self._base_nodes: Dict[str, ModelNode] = {}
        if model.root_node:
            for n in model.all_nodes():
                self._base_nodes[n.name.lower()] = n
        # Cross-fade transition blending state
        self._blend_from_pose: Optional[AnimPose] = None
        self._blend_t:         float = 0.0   # blend fraction [0.0 → 1.0]
        self._blend_duration:  float = 0.0   # total blend duration in seconds
        # Fired-event tracking so each event fires exactly once per loop
        self._fired_events: set = set()  # indices into current_anim.events

    # ── Playback control ────────────────────────────────────────────────────

    @property
    def current_animation(self) -> Optional[Animation]:
        return self._current_anim

    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def current_time(self) -> float:
        return self._time

    def play(self, anim_name: str, loop: bool = True, blend: bool = True):
        """Start playing the named animation.

        If *blend* is True and an animation is already active, captures a
        pose snapshot and cross-fades from it to the new animation over the
        new animation's ``transition_time`` seconds.
        """
        anim = self._find_anim(anim_name)
        if anim is None:
            log.warning(f"Animation '{anim_name}' not found in model '{self.model.name}'")
            return False
        # Cross-fade: capture current pose before switching
        if blend and self._playing and self._current_anim is not None:
            self._blend_from_pose = self.evaluate()
            self._blend_t         = 0.0
            self._blend_duration  = max(0.0, anim.transition_time)
        else:
            self._blend_from_pose = None
            self._blend_t         = 0.0
            self._blend_duration  = 0.0
        self._current_anim = anim
        self._loop         = loop
        self._playing      = True
        self._time         = 0.0
        self._fired_events = set()
        return True

    def stop(self):
        self._playing = False

    def pause(self):
        self._playing = not self._playing

    def seek(self, t: float):
        if self._current_anim:
            length = max(0.001, self._current_anim.length)
            self._time = t % length if self._loop else min(t, length)
            # Reset fired-events so events before the new position don't re-fire
            self._fired_events = set()
            # Cancel any in-progress blend when manually seeking
            self._blend_from_pose = None
            self._blend_t         = 0.0
            self._blend_duration  = 0.0

    def advance(self, dt: float) -> bool:
        """Advance animation time by *dt* seconds.

        Returns ``True`` if playback is **still active** after the advance,
        ``False`` when the animation has ended (non-looping) or was not
        playing at all.
        """
        if not self._playing or not self._current_anim:
            return False
        length = max(0.001, self._current_anim.length)
        self._time += dt

        # ── Fire time-based events (once per loop cycle) ─────────────────────
        for ei, ev in enumerate(self._current_anim.events):
            if ev.time <= self._time and ei not in self._fired_events:
                self._fired_events.add(ei)
                log.debug(f"AnimEvent '{ev.name}' fired @ {ev.time:.3f}s")

        # ── Advance cross-fade blend ──────────────────────────────────────────
        if self._blend_duration > 0.0:
            self._blend_t = min(1.0, self._time / self._blend_duration)
            if self._blend_t >= 1.0:
                self._blend_from_pose = None  # blend finished
                self._blend_t         = 0.0
                self._blend_duration  = 0.0

        # ── Loop / stop ───────────────────────────────────────────────────────
        if self._time >= length:
            if self._loop:
                self._time %= length
                self._fired_events = set()  # reset so events fire again
            else:
                self._time    = length
                self._playing = False
        return self._playing

    # ── Pose evaluation ─────────────────────────────────────────────────────

    def evaluate(self, t: Optional[float] = None) -> AnimPose:
        """
        Evaluate the animation pose at time *t* (defaults to current time).

        When a cross-fade blend is active, the returned pose is smoothly
        interpolated (lerp position / slerp rotation) from the captured
        ``_blend_from_pose`` towards the new animation pose using the
        current ``_blend_t`` fraction [0 = old, 1 = new].

        Returns an :class:`AnimPose` with all animated node transforms.
        """
        if t is None:
            t = self._time
        anim = self._current_anim
        if anim is None:
            return AnimPose(time=t)

        pose = AnimPose(time=t)
        for anim_node in anim.nodes:
            np_ = self._eval_node(anim_node, t)
            if np_:
                pose.nodes[np_.name.lower()] = np_

        # ── Cross-fade blend ──────────────────────────────────────────────────
        if self._blend_from_pose is not None and 0.0 < self._blend_t < 1.0:
            alpha = self._blend_t  # 0 = fully old pose, 1 = fully new pose
            for name, new_np in list(pose.nodes.items()):
                old_np = self._blend_from_pose.nodes.get(name)
                if old_np is None:
                    continue
                # Lerp position
                op = old_np.position; npos = new_np.position
                blended_pos = (
                    op[0] + (npos[0] - op[0]) * alpha,
                    op[1] + (npos[1] - op[1]) * alpha,
                    op[2] + (npos[2] - op[2]) * alpha,
                )
                # Slerp rotation (shortest-path)
                blended_rot = tuple(
                    _slerp(list(old_np.rotation), list(new_np.rotation), alpha)
                )
                # Lerp scale
                blended_scale = old_np.scale + (new_np.scale - old_np.scale) * alpha
                # Lerp alpha (None means "use bind-pose value")
                if old_np.alpha is not None and new_np.alpha is not None:
                    blended_alpha: Optional[float] = old_np.alpha + (new_np.alpha - old_np.alpha) * alpha
                elif new_np.alpha is not None:
                    blended_alpha = new_np.alpha
                else:
                    blended_alpha = old_np.alpha
                # Lerp selfillum
                if old_np.selfillum is not None and new_np.selfillum is not None:
                    osi = old_np.selfillum; nsi = new_np.selfillum
                    blended_si: Optional[Tuple[float,float,float]] = (
                        osi[0] + (nsi[0]-osi[0])*alpha,
                        osi[1] + (nsi[1]-osi[1])*alpha,
                        osi[2] + (nsi[2]-osi[2])*alpha,
                    )
                elif new_np.selfillum is not None:
                    blended_si = new_np.selfillum
                else:
                    blended_si = old_np.selfillum
                pose.nodes[name] = NodePose(
                    name      = new_np.name,
                    position  = blended_pos,
                    rotation  = blended_rot,
                    scale     = blended_scale,
                    alpha     = blended_alpha,
                    selfillum = blended_si,
                )

        return pose

    def _eval_node(self, anim_node: ModelNode, t: float) -> Optional[NodePose]:
        """Evaluate a single animation node at time t.

        KotOR animation coordinate conventions
        ──────────────────────────────────────
        POSITION controller (type 8):
            Keyframe values are DELTA OFFSETS in parent-local space, added to the
            node's bind-pose local position.  They are NOT absolute positions.
            Formula:  animated_local_pos = bind_local_pos + keyframe_delta

            Verified against both xoreos (model_kotor.cpp, arePositionFramesRelative()
            always returns true) and KotorBlender (animnode.py,
            convert_mdl_position_to_bl_location: p1 = restloc + animscale * val).

            Evidence:
              c_bantha BTHips:  bind=(0,-1.096,1.619), k0=(0,0,0)
                → animated=(0,-1.096,1.619)  [bone stays at bind = T-pose] ✓
              c_bantha BTSpine1: bind=(0,-0.436,1.557), k0=(0.055,-0.004,-0.003)
                → animated=(0.055,-0.44,1.555)  [small walking nudge] ✓
              c_bmspecdiff RootDummy: bind=(0,0.137,0.962), k0=(-0.028,-0.009,0.962)
                → animated=(-0.028,0.128,1.924)  [creature rises to active stance] ✓
              c_kinrath RootDummy: bind=(-0.002,-0.138,0.6), k0=(-0.044,0,-0.076)
                → animated=(-0.046,-0.138,0.524)  [step forward] ✓

            NOTE: Treating these as absolute would collapse all bones toward the
            origin (the 'exploded skeleton' bug).

        ORIENTATION controller (type 20):
            Keyframe values are ABSOLUTE quaternions in parent-local space.
            They REPLACE the bind-pose local rotation entirely.
            Evidence: BTHips bind=[0,0,0,1] (identity), anim=[0.001,0.061,-0.07,0.996]
            (small rotation from T-pose) — clearly an absolute rotation, not a
            multiplication of the bind rotation by the keyframe.
        """
        # Start with base-pose values
        base = self._base_nodes.get(anim_node.name.lower())
        pos  = list(base.position) if base else [0.0, 0.0, 0.0]
        rot  = list(base.rotation) if base else [0.0, 0.0, 0.0, 1.0]
        scale = 1.0

        # Normalize base rotation to unit length only.
        # NOTE: We do NOT canonicalize to positive-w here.  xoreos stores some
        # bind-pose quaternions with negative w (e.g. r_shlder: w=-0.2266), and
        # some animation keyframes also have negative w.  Flipping the sign of
        # the BASE pose quaternion so w>0 would make it inconsistent with the
        # keyframe signs, causing _slerp to compute a longer-path interpolation
        # through the antipodal instead of the geodesic. The _slerp function
        # already handles shortest-path via "if dot < 0: negate q2; dot=-dot".
        # Verified against xoreos animation.cpp interpolateOrientation().
        if base:
            r2 = rot[0]*rot[0] + rot[1]*rot[1] + rot[2]*rot[2] + rot[3]*rot[3]
            if r2 > 1e-9 and abs(r2 - 1.0) > 1e-4:
                rs = math.sqrt(r2)
                rot = [rot[0]/rs, rot[1]/rs, rot[2]/rs, rot[3]/rs]

        # Material animation accumulators (None = no keyframe found)
        node_alpha_anim: Optional[float]                    = None
        node_si_anim:    Optional[Tuple[float,float,float]] = None

        for ctrl in anim_node.controllers:
            ctype = ctrl['type']
            val = _interp_channel(ctrl['times'], ctrl['values'], t)
            if val is None:
                continue

            if ctype == self.CTRL_POSITION and len(val) >= 3:
                # KotOR position keyframes are DELTA OFFSETS added to bind-pose
                # local position (NOT absolute positions).  Verified against xoreos
                # (arePositionFramesRelative()=true) and KotorBlender (animnode.py).
                # Validate: reject non-finite position delta values
                if all(math.isfinite(v) for v in val[:3]):
                    pos = [pos[0] + val[0], pos[1] + val[1], pos[2] + val[2]]
            elif ctype == self.CTRL_ORIENTATION and len(val) >= 4:
                # KotOR orientation keyframes are ABSOLUTE quaternions (replace bind rot).
                # Validate and normalize animated rotation.
                # NOTE: Do NOT canonicalize to positive-w. xoreos stores negative-w
                # quaternions in some animation data; the _slerp function handles
                # shortest-path via "if dot < 0: negate q2". Forcing positive-w here
                # would cause incorrect long-path interpolations between consecutive
                # keyframes that straddle the w=0 boundary.
                rv = val[:4]
                if all(math.isfinite(v) for v in rv):
                    r2 = rv[0]*rv[0] + rv[1]*rv[1] + rv[2]*rv[2] + rv[3]*rv[3]
                    if r2 > 1e-9:
                        rs = math.sqrt(r2)
                        rot = [rv[0]/rs, rv[1]/rs, rv[2]/rs, rv[3]/rs]
                    else:
                        rot = [0.0, 0.0, 0.0, 1.0]  # fallback identity
            elif ctype == self.CTRL_SCALE and len(val) >= 1:
                sv = val[0]
                if math.isfinite(sv) and sv > 0:
                    scale = sv
            elif ctype == self.CTRL_ALPHA and len(val) >= 1:
                av = val[0]
                if math.isfinite(av):
                    node_alpha_anim = max(0.0, min(1.0, av))
                else:
                    node_alpha_anim = None
            elif ctype == self.CTRL_ALPHA_XOREOS and len(val) >= 1:
                # xoreos uses CTRL_ALPHA = 128; handle alongside KotorBlender's 132
                av = val[0]
                if math.isfinite(av) and node_alpha_anim is None:
                    node_alpha_anim = max(0.0, min(1.0, av))
            elif ctype == self.CTRL_SELFILLUMCOLOR and len(val) >= 3:
                sv0, sv1, sv2 = val[0], val[1], val[2]
                if math.isfinite(sv0) and math.isfinite(sv1) and math.isfinite(sv2):
                    node_si_anim = (max(0.0,sv0), max(0.0,sv1), max(0.0,sv2))
                else:
                    node_si_anim = None

        # Canonicalize output rotation to positive-w before returning the pose.
        # This prevents 360° flips when the pose is used as the slerp start-point
        # in the viewport's _node_world_transform chain.  The canonicalization
        # happens at the OUTPUT stage (after all controllers are applied) so it
        # does NOT affect the intermediate slerp consistency between keyframes.
        # The _slerp function handles shortest-path via "if dot < 0: negate q2"
        # independently; this canonicalization ensures the base-pose start-point
        # for the NEXT slerp evaluation has a predictable positive-w form.
        # Reference: test_v37_bug_fixes.py TestViewportWCanonicalization.
        if rot[3] < 0.0:
            rot = [-rot[0], -rot[1], -rot[2], -rot[3]]

        return NodePose(
            name      = anim_node.name,
            position  = tuple(pos),
            rotation  = tuple(rot),
            scale     = scale,
            alpha     = node_alpha_anim,
            selfillum = node_si_anim,
        )

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _find_anim(self, name: str) -> Optional[Animation]:
        nl = name.lower()
        for a in self.model.animations:
            if a.name.lower() == nl:
                return a
        return None

    def list_animations(self) -> List[Dict[str, Any]]:
        """Return list of animation info dicts."""
        result = []
        for a in self.model.animations:
            # Count total keyframes across all nodes
            total_keys = sum(
                len(c['times'])
                for n in a.nodes
                for c in n.controllers
            )
            result.append({
                'name':       a.name,
                'length':     a.length,
                'trans_time': a.transition_time,
                'node_count': len(a.nodes),
                'key_count':  total_keys,
                'event_count':len(a.events),
                'anim_root':  a.anim_root,
            })
        return result

    def get_animation_fps_estimate(self, anim: Animation) -> float:
        """Estimate FPS from keyframe density."""
        if not anim.nodes or anim.length <= 0:
            return 30.0
        max_keys = 0
        for n in anim.nodes:
            for c in n.controllers:
                max_keys = max(max_keys, len(c['times']))
        if max_keys <= 1:
            return 30.0
        return round(max_keys / anim.length)

    # ── Export ───────────────────────────────────────────────────────────────

    def export_animation_json(self, anim_name: str, output_path: str) -> bool:
        """Export a single animation to JSON format."""
        anim = self._find_anim(anim_name)
        if anim is None:
            log.error(f"Animation '{anim_name}' not found")
            return False

        data = {
            'format':      'kotor_animation_v1',
            'model_name':  self.model.name,
            'name':        anim.name,        # convenience alias
            'anim_name':   anim.name,
            'length':      anim.length,
            'trans_time':  anim.transition_time,
            'anim_root':   anim.anim_root,
            'fps_estimate': self.get_animation_fps_estimate(anim),
            'events': [
                {'time': ev.time, 'name': ev.name}
                for ev in anim.events
            ],
            'nodes': []
        }

        for n in anim.nodes:
            ndata = {
                'name':        n.name,
                'base_position': list(n.position),
                'base_rotation': list(n.rotation),
                'controllers': []
            }
            for ctrl in n.controllers:
                ndata['controllers'].append({
                    'type':    ctrl['type'],
                    'name':    ctrl['name'],
                    'columns': ctrl['columns'],
                    'times':   ctrl['times'],
                    'values':  [list(v) for v in ctrl['values']],
                })
            data['nodes'].append(ndata)

        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        log.info(f"Exported animation '{anim_name}' → {output_path}")
        return True

    def export_animation_bvh(self, anim_name: str, output_path: str) -> bool:
        """
        Export animation to BVH (BioVision Hierarchy) format.
        BVH is widely supported by Blender, Maya, MotionBuilder, etc.
        """
        anim = self._find_anim(anim_name)
        if anim is None:
            log.error(f"Animation '{anim_name}' not found")
            return False

        fps = max(15.0, min(120.0, self.get_animation_fps_estimate(anim)))
        frame_count = max(1, int(anim.length * fps))
        frame_time  = 1.0 / fps

        # Build bone list in hierarchy order from model
        bones = []
        if self.model.root_node:
            def _collect_bones(node, depth=0):
                bones.append((node, depth))
                for c in node.children:
                    _collect_bones(c, depth + 1)
            _collect_bones(self.model.root_node)

        if not bones:
            log.error("No bones found in model")
            return False

        lines = []

        # HIERARCHY section
        lines.append("HIERARCHY")

        # Build anim_node set BEFORE hierarchy so _bvh_bone can detect animated leaves
        # BUG-03 FIX: a leaf node that has animation keys is a real JOINT and must
        # receive CHANNELS in the hierarchy section (and frame data in MOTION section).
        # Only promote it to a proper JOINT; a synthetic end-site child is appended so
        # the BVH is still syntactically valid (every non-leaf JOINT must close with a
        # child "End Site" or another JOINT).
        anim_nodes_set: set = {n.name.lower() for n in anim.nodes}

        def _bvh_bone(node, depth):
            indent = "  " * depth
            is_root = (node.parent is None)
            is_true_leaf = (not node.children)
            # BUG-03: an animated leaf is treated as a JOINT, not an End Site
            is_animated_leaf = is_true_leaf and node.name.lower() in anim_nodes_set

            if is_root:
                lines.append(f"{indent}ROOT {node.name}")
            elif is_true_leaf and not is_animated_leaf:
                # Pure End Site — no channels, no frame data
                lines.append(f"{indent}End Site")
                lines.append(f"{indent}{{")
                px, py, pz = node.position
                lines.append(f"{indent}  OFFSET {px:.6f} {py:.6f} {pz:.6f}")
                lines.append(f"{indent}}}")
                return
            else:
                lines.append(f"{indent}JOINT {node.name}")

            lines.append(f"{indent}{{")
            px, py, pz = node.position
            lines.append(f"{indent}  OFFSET {px:.6f} {py:.6f} {pz:.6f}")

            if is_root:
                lines.append(f"{indent}  CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation")
            else:
                lines.append(f"{indent}  CHANNELS 3 Zrotation Xrotation Yrotation")

            for child in node.children:
                _bvh_bone(child, depth + 1)

            # BUG-03: animated leaf — append synthetic End Site so BVH is valid
            if is_animated_leaf:
                lines.append(f"{indent}  End Site")
                lines.append(f"{indent}  {{")
                lines.append(f"{indent}    OFFSET 0.000000 0.000000 0.000000")
                lines.append(f"{indent}  }}")

            lines.append(f"{indent}}}")

        _bvh_bone(self.model.root_node, 0)

        # MOTION section
        lines.append("MOTION")
        lines.append(f"Frames: {frame_count}")
        lines.append(f"Frame Time: {frame_time:.6f}")

        # Build anim_node lookup (already defined anim_nodes_set above for hierarchy)
        anim_nodes: Dict[str, ModelNode] = {n.name.lower(): n for n in anim.nodes}

        def _quat_to_euler_zxy(q: List[float]) -> Tuple[float, float, float]:
            """Convert quaternion to ZXY Euler angles in degrees (BVH convention)."""
            x, y, z, w = q
            # Normalize
            mag = math.sqrt(x*x + y*y + z*z + w*w)
            if mag > 1e-9:
                x /= mag; y /= mag; z /= mag; w /= mag

            # ZXY order: R = Rz * Rx * Ry
            sinX = 2*(w*x + y*z)
            cosX = 1 - 2*(x*x + y*y)
            rx = math.atan2(sinX, cosX)

            sinY = 2*(w*y - z*x)
            sinY = max(-1.0, min(1.0, sinY))
            ry = math.asin(sinY)

            sinZ = 2*(w*z + x*y)
            cosZ = 1 - 2*(y*y + z*z)
            rz = math.atan2(sinZ, cosZ)

            return (
                math.degrees(rz),
                math.degrees(rx),
                math.degrees(ry),
            )

        for fi in range(frame_count):
            t = fi * frame_time
            frame_vals = []

            def _collect_frame(node, is_root=False):
                anim_n = anim_nodes.get(node.name.lower())
                base   = self._base_nodes.get(node.name.lower())

                # Get position
                pos = list(base.position) if base else [0.0, 0.0, 0.0]
                rot = list(base.rotation) if base else [0.0, 0.0, 0.0, 1.0]

                if anim_n:
                    ctrl_pos_t, ctrl_pos_v = _get_ctrl(anim_n, AnimationEngine.CTRL_POSITION)
                    ctrl_rot_t, ctrl_rot_v = _get_ctrl(anim_n, AnimationEngine.CTRL_ORIENTATION)
                    ev_pos = _interp_channel(ctrl_pos_t, ctrl_pos_v, t)
                    ev_rot = _interp_channel(ctrl_rot_t, ctrl_rot_v, t)
                    if ev_pos and len(ev_pos) >= 3 and all(math.isfinite(v) for v in ev_pos[:3]):
                        # BUG-05 FIX: position keys are DELTA offsets, not absolute.
                        # Must add to bind-pose position (same formula as _eval_node).
                        pos = [pos[i] + ev_pos[i] for i in range(3)]
                    if ev_rot and len(ev_rot) >= 4:
                        rot = ev_rot[:4]

                ez, ex, ey = _quat_to_euler_zxy(rot)

                if is_root:
                    frame_vals.extend([pos[0], pos[1], pos[2], ez, ex, ey])
                else:
                    frame_vals.extend([ez, ex, ey])

                for child in node.children:
                    # BUG-03 FIX: only skip true End Site nodes (no children AND not animated).
                    # Animated leaf joints were incorrectly skipped, losing their keyframe data.
                    if not child.children and child.name.lower() not in anim_nodes_set:
                        continue   # skip pure end sites (no channels in hierarchy)
                    _collect_frame(child)

            _collect_frame(self.model.root_node, is_root=True)
            lines.append(" ".join(f"{v:.6f}" for v in frame_vals))

        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='ascii') as f:
            f.write('\n'.join(lines) + '\n')
        log.info(f"Exported BVH '{anim_name}' ({frame_count} frames @ {fps:.0f}fps) → {output_path}")
        return True

    def export_all_animations(self, output_dir: str,
                               fmt: str = 'json') -> List[str]:
        """Export all animations to the given directory. Returns list of output paths."""
        os.makedirs(output_dir, exist_ok=True)
        exported = []
        for anim in self.model.animations:
            safe_name = anim.name.replace('/', '_').replace('\\', '_')
            if fmt == 'bvh':
                path = os.path.join(output_dir, f"{safe_name}.bvh")
                ok = self.export_animation_bvh(anim.name, path)
            else:
                path = os.path.join(output_dir, f"{safe_name}.json")
                ok = self.export_animation_json(anim.name, path)
            if ok:
                exported.append(path)
        return exported

    # ── Import ───────────────────────────────────────────────────────────────

    def import_animation_json(self, json_path: str) -> Optional[Animation]:
        """Import an animation from a JSON file (previously exported)."""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if data.get('format') not in ('kotor_animation_v1', None):
                log.warning(f"Unknown animation format: {data.get('format')}")

            anim = Animation(
                name            = data.get('anim_name', os.path.basename(json_path)),
                length          = float(data.get('length', 1.0)),
                transition_time = float(data.get('trans_time', 0.25)),
                anim_root       = data.get('anim_root', ''),
            )

            for ev_data in data.get('events', []):
                anim.events.append(AnimEvent(
                    time = float(ev_data.get('time', 0.0)),
                    name = ev_data.get('name', ''),
                ))

            for n_data in data.get('nodes', []):
                from .model_data import ModelNode, NodeFlags
                node = ModelNode(
                    name     = n_data.get('name', 'node'),
                    position = tuple(n_data.get('base_position', [0,0,0])),
                    rotation = tuple(n_data.get('base_rotation', [0,0,0,1])),
                )
                for c_data in n_data.get('controllers', []):
                    node.controllers.append({
                        'type':    int(c_data.get('type', 0)),
                        'name':    c_data.get('name', ''),
                        'columns': int(c_data.get('columns', 1)),
                        'times':   [float(t) for t in c_data.get('times', [])],
                        'values':  [list(v) for v in c_data.get('values', [])],
                    })
                anim.nodes.append(node)

            log.info(f"Imported animation '{anim.name}' from {json_path}")
            return anim

        except Exception as e:
            log.error(f"Failed to import animation from {json_path}: {e}")
            return None

    def get_pose(self, t: Optional[float] = None) -> AnimPose:
        """Alias for evaluate() – returns an AnimPose at time t (or current time).
        Provided for convenience so callers can use either name."""
        return self.evaluate(t)

    def get_fired_events(self) -> List[str]:
        """Return names of events that have fired so far in the current loop cycle."""
        if not self._current_anim:
            return []
        return [
            self._current_anim.events[i].name
            for i in sorted(self._fired_events)
            if i < len(self._current_anim.events)
        ]

    def is_blending(self) -> bool:
        """Return True if a cross-fade blend is currently active."""
        return self._blend_from_pose is not None and self._blend_t < 1.0

    def blend_fraction(self) -> float:
        """Return the current blend fraction [0.0 = start of blend, 1.0 = complete]."""
        return self._blend_t

    def add_animation(self, anim: Animation):
        """Add an animation to the model's animation list."""
        # Replace if same name exists
        for i, a in enumerate(self.model.animations):
            if a.name.lower() == anim.name.lower():
                self.model.animations[i] = anim
                log.info(f"Replaced animation '{anim.name}'")
                return
        self.model.animations.append(anim)
        log.info(f"Added animation '{anim.name}' to model '{self.model.name}'")

    def remove_animation(self, anim_name: str) -> bool:
        """Remove an animation by name."""
        for i, a in enumerate(self.model.animations):
            if a.name.lower() == anim_name.lower():
                del self.model.animations[i]
                if self._current_anim and self._current_anim.name.lower() == anim_name.lower():
                    self._current_anim = None
                    self._playing = False
                return True
        return False


# ─────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────

def _get_ctrl(node: ModelNode, ctrl_type: int) -> Tuple[List, List]:
    """Get (times, values) for a controller type. Returns empty lists if not found."""
    for c in node.controllers:
        if c['type'] == ctrl_type:
            return c['times'], c['values']
    return [], []
