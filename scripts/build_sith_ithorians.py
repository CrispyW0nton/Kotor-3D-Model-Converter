"""Build the K1 Sith Ithorian Lorum Ipsat package (T2556-T2571).

The active T2571 target is the high-fidelity ``c_ithlord`` OBJ. It is fit
against the K1 ``c_ithorian`` donor (anim_scale 1.0, supermodel NULL -> 16
self-contained clips), rigged, anatomically split, gated, and exported with
the complete local combat inventory. The package adds one appearance.2da row
cloned from vanilla Ithorian row 72, one hostile UTC, and visual confirmation
renders. Historical ``c_ithschol`` outputs from the earlier two-variant build
may remain in ``OUT``; this focused builder neither deploys nor deletes them.

- ``<resref>_fit_front.png`` / ``_fit_side.png``  — bind mesh + fitted skeleton
- ``<resref>_anim_<clip>.png``                    — LBS-deformed pose samples
  produced through the SAME MatrixPaletteUploader path the viewport uses
  (T2555: G5 compact-slot rows).

Gates carried over from build_dathomir_rancor.py: inverse-bind contract
(build + reload), seam weight weld, geometry-header resref, anim_root
consistency, texture <=2048 + vertical flip (T2551/T2552), vanilla-2DA
duplicate-row guard.  New gates: native bone survival (T2555 NeckUpr_g
orphan regression) and a full 16-clip deformation audit (no exploded
vertices / missing bone transforms on any sample).
"""
from __future__ import annotations

import json
import os
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for rel in (
    "native/GhostRigger.Core.Workflow/Python",
    "native/GhostRigger.Core.Math/Python",
    "native/GhostRigger.Core.Resources/Python",
    "native/GhostRigger.Core.IO/Python",
    "native/GhostRigger.Core.Project/Python",
    "native/GhostRigger.Core.Scene/Python",
    "native/GhostRigger.Core.Validation/Python",
    "native/GhostRigger.Core.Rendering/Python",
    "native/GhostRigger.Core.Unreal/Python",
    "native/GhostRigger.Core.Tools/Python",
    "",
):
    p = str(ROOT / rel) if rel else str(ROOT)
    if p not in sys.path:
        sys.path.insert(0, p)

K1 = r"C:\Program Files (x86)\Steam\steamapps\common\swkotor"
SRC = pathlib.Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\HighFidelityKotorCharacters"
    r"\SithIthorianScholar"
)
OUT = SRC / "MDL"
DONOR = "c_ithorian"
# T2562: combat contract.  The creature fallback resolver can request
# g0a1/g0a2 (animations.2da rows 276/277, Ghidra CSWCCreature::
# UpdateMeleeAttackData base+0x114) and creadyr for combat-ready — clips the
# vanilla Ithorian lacks entirely (it never fights).  Bake them as LOCAL
# animations retargeted from the S_Female02 combat set (user-selected motion
# source; bone names are shared).  Dialogue/idle clips stay untouched.
# T2565: the Ithorian carries the FULL N_DarkJediM animation inventory —
# every clip resolvable through its supermodel chain (S_Female02 ->
# S_Female01 -> S_Male02 -> S_Male01, 267 effective clips), each retargeted
# world-space onto the Ithorian skeleton and baked as a LOCAL animation.
# The 16 native Ithorian clips win on name collisions (dialogue/idles keep
# their authored motion).
ANIMATION_DONOR_BODY = "N_DarkJediM"
MALAK_COMBAT_DONOR = "N_DarthMalak"
# T2572: K1 has no UTC "combat set" selector.  Route the creature fallback
# g0a1/g0a2/creadyr slots to Malak's local Set-2 vocabulary in addition to the
# Set-2-shaped F-model weapon slots below.  Synchronized attack audio markers
# are inappropriate on the solo creature aliases and are stripped below.
COMBAT_ALIAS_SOURCES = {
    "g0a1": "c2a1",
    "g0a2": "c2a2",
    "creadyr": "g2r1",
}
# Historical T2571 mapping retained only to preserve the wider optional Set 4
# preview inventory and its proven morphology corrections.  T2572 overrides
# every Malak-owned engine-facing target after this map is assembled.
ANIMATION_SOURCE_OVERRIDES = {
    **{f"c2a{i}": f"c4a{i}" for i in range(1, 7)},
    **{f"c2d{i}": f"c4d{i}" for i in range(1, 6)},
    **{f"c2n{i}": f"c4n{i}" for i in range(1, 3)},
    **{f"c2p{i}": f"c4p{i}" for i in range(1, 6)},
    **{f"f2a{i}": f"f4a{i}" for i in range(1, 5)},
    **{f"f2d{i}": f"f4d{i}" for i in range(1, 4)},
    **{f"f2p{i}": f"f4p{i}" for i in range(1, 4)},
    **{f"g2{suffix}": f"g4{suffix}" for suffix in (
        "a1", "a2", "d1", "f1", "g1", "r1", "w1",
    )},
    **{f"m2{suffix}": f"m4{suffix}" for suffix in (
        "a1", "a2", "d1", "d2", "g1", "g2",
    )},
}
# T2572: the external-weapon Sith Ithorian now uses N_DarthMalak's actual
# self-contained combat vocabulary.  Keep the wider N_DarkJediM inventory as
# optional local coverage, but these engine-facing slots take precedence. Malak
# has five c2 attacks; K1 can request c2a6, so that final slot deliberately
# repeats his fifth attack instead of falling back to another actor's motion.
MALAK_COMBAT_SLOT_SOURCES = {
    **{f"c2a{i}": f"c2a{i}" for i in range(1, 6)},
    "c2a6": "c2a5",
    **{f"c2p{i}": f"c2p{i}" for i in range(1, 6)},
    **{f"c2d{i}": f"c2d{i}" for i in range(1, 6)},
    **{f"c2n{i}": f"c2n{i}" for i in range(1, 3)},
    **{f"f2a{i}": f"f2a{i}" for i in range(1, 5)},
    **{f"f2d{i}": f"f2d{i}" for i in range(1, 4)},
    **{f"f2p{i}": f"f2p{i}" for i in range(1, 4)},
    "g2r1": "g2r1",
    "g2w1": "g2w1",
    "tlkforce": "tlkforce",
    **{f"castout{i}": f"castout{i}" for i in range(1, 4)},
    **{f"castoutlp{i}": f"castoutlp{i}" for i in range(1, 4)},
    "choke": "choke",
    "fear": "fear",
    "horror": "horror",
    "sleep": "sleep",
    "whirlwind": "whirlwind",
    "throwsab": "throwsab",
    "throwsablp": "throwsablp",
    "catchsab": "catchsab",
    "g1x1": "g1x1",
    "g1y1": "g1y1",
    "g1z1": "g1z1",
    "taunt": "taunt",
    "kd": "kd",
}
# Every Set 4 motion exists twice in the shipped model: under its authored
# source name for preview/debugging and under the Set 2 name K1 can request for
# a single-saber creature.  The three creature aliases are additional runtime
# entry points.  Keep the complete set explicit so morphology corrections are
# deterministic and source/target payload parity can be proven after rewrite.
SET4_ASSIGNED_SOURCE_CLIPS = frozenset(
    str(name).lower() for name in ANIMATION_SOURCE_OVERRIDES.values()
)
SET4_ASSIGNED_TARGET_CLIPS = frozenset({
    *(str(name).lower() for name in ANIMATION_SOURCE_OVERRIDES),
    *(str(name).lower() for name in COMBAT_ALIAS_SOURCES),
})
SET4_ASSIGNED_CLIPS = frozenset(
    SET4_ASSIGNED_SOURCE_CLIPS | SET4_ASSIGNED_TARGET_CLIPS
)
assert len(SET4_ASSIGNED_SOURCE_CLIPS) == 41
assert len(SET4_ASSIGNED_TARGET_CLIPS) == 44
assert len(SET4_ASSIGNED_CLIPS) == 85
ANIMATION_EVENT_EXCLUDE_BY_TARGET = {
    "g0a1": {"clash", "contact", "hitparry"},
    "g0a2": {"clash", "contact", "hitparry"},
}
# T2572: Lorum must remain appearance modeltype F so K1 uses the external
# right-hand weapon attachment path for Malak's saber. That same modeltype
# makes the engine request humanoid pause/death names instead of the creature-
# prefixed names used by stock modeltype-S Ithorians. Mirror the native payloads
# into the F-facing slots so Pause2 keeps the hand-to-chin thinking gesture
# and the corpse uses the stock Ithorian arm silhouette.
# T2573: animations.2da also carries death VARIANT rows the engine can select
# instead of plain die/dead — die1/dead1 (rows 82/83) and die3/dead3 (rows
# 374/375). The baked humanoid payloads under those names played with the
# Ithorian's long arms locked upward on the corpse, so every death-facing slot
# now mirrors the native cdie/cdead motion.
# T2574: the knockdown-recovery slots getupdead/getupdead1 (rows 381/382)
# likewise held humanoid retargets; the stock Ithorian's own get-up is
# cgustandb, so both slots mirror it.
MODELTYPE_F_NATIVE_STATE_ALIASES = {
    "pause1": "cpause1",
    "pause2": "cpause2",
    "die": "cdie",
    "dead": "cdead",
    "die1": "cdie",
    "dead1": "cdead",
    "die3": "cdie",
    "dead3": "cdead",
    "getupdead": "cgustandb",
    "getupdead1": "cgustandb",
}
# T2568: clips that need morphology-aware arm endpoint retargeting.  These are
# the saber attacks/guards the user evaluates side-by-side, plus the Force and
# saber-throw gestures that put a hand near the Ithorian's forward-projecting
# head.  Native Ithorian dialogue/idle clips remain untouched.
BASE_ARM_POSITION_GOAL_CLIPS = {
    "castout1", "castout2", "castout3",
    "castoutlp1", "castoutlp2", "castoutlp3",
    "catchsab", "throwsab", "throwsablp", "tlkforce",
}
COMBAT_SET2_DEFEND_CLIPS = {
    "c2d1", "c2d2", "c2d3", "c2d4", "c2d5",
}
# Defend clips keep the Dark Jedi's authored saber angle, but the Ithorian's
# forward skull occupies space the humanoid never had to clear.  Translate the
# two-hand grip as one continuous unit so the complete visible blade plane is
# safe without tearing the off hand away from the hilt.
SABER_SURFACE_GOAL_CLIPS = set(COMBAT_SET2_DEFEND_CLIPS)
LOW_LEFT_ELBOW_GOAL_CLIPS = set()
SABER_SURFACE_GOAL_CLEARANCE = 0.15
# Binary quaternion interpolation makes f4a2's 120 Hz midpoint sit 0.23 mm
# below the 0.12 m rendered-surface floor when its 60 Hz plan keys use the
# ordinary 0.15 m margin.  Tighten only this canonical equivalence class; its
# c2/g0 aliases reuse the same correction trajectory exactly.
SET4_SABER_SURFACE_CLEARANCE_BY_SOURCE = {
    "f4a2": 0.155,
}
# The front/right atlas can hide a blade that crosses the upper-body skin in
# depth.  These canonical Set 4 motions were the only classes below the
# rendered blade-plane floor in a core-body triangle scan.  Give just those
# classes an exact dynamic skin-surface goal; targets and runtime aliases reuse
# the canonical correction path.
SET4_SABER_BODY_SURFACE_CLEARANCE_BY_SOURCE = {
    "c4a2": 0.15,
    "c4n2": 0.15,
    "f4a1": 0.15,
    "f4d1": 0.15,
    "m4d2": 0.15,
}
# Durable Set 4 checkpoints for those five clips are valid only for this exact
# skin-face selector.  Keep the token source-scoped so the other 36 canonical
# plans retain their already-proven cache identities.
SET4_CORE_BODY_SURFACE_POLICY_REVISION = (
    "v1:torso-neck-backpack-weights:all-vertices-ge-0.75"
)
SET4_BODY_SURFACE_REVIEW_FRACTIONS = (
    0.02, 0.20, 0.40, 0.4318, 0.60, 0.80, 0.98,
)
RIGHT_SABER_BODY_CLEARANCE_MIN = 0.12
SABER_SURFACE_CLEARANCE_BY_CLIP = {
    "c2d2": 0.165,
    "c2d4": 0.12,
}
LEFT_ELBOW_WRIST_MARGIN = 0.04
COUPLED_DEFEND_VELOCITY_WEIGHT = 0.004
COUPLED_DEFEND_MAX_CORRECTION_SPEED = 5.0
COUPLED_CONTINUATION_CLEARANCE_BY_CLIP = {
    "c2d2": 0.125,
    "c2d3": 0.12,
    "c2d4": 0.12,
}
COUPLED_CONTINUATION_CELL_SIZE = 0.0025
COUPLED_CONTINUATION_BEAM_WIDTH = 72
COUPLED_CONTINUATION_BEAM_WIDTH_BY_CLIP = {"c2d3": 144}
COUPLED_CONTINUATION_WINDOW_PADDING = 48
COUPLED_CONTINUATION_END_ANCHOR_CLIPS = {"c2d3"}
COUPLED_CONTINUATION_TRANSITION_SUBSTEPS = 4
# Folded-arm quaternion interpolation is nonlinear even when the shared hand
# path is smooth.  Bake the three measured outliers at 480 Hz; their dense
# gates sample the midpoints again at 960 Hz.  The narrowly scoped drift limits
# cover sub-millisecond residuals while every 60 Hz playback sample lands on an
# exact coupled solve key.
COUPLED_BAKE_RATE_BY_CLIP = {
    "c2d1": 480.0,
    "c2d2": 480.0,
    "c2d3": 480.0,
}
# c2d2 needs 480 Hz arm keys to constrain nonlinear shoulder/forearm FK, but
# its exact collision search remains tractable and sufficient at 240 Hz.  c2d4
# has a disconnected 120 Hz planner state graph around 22%; plan its skull
# detour at 30 Hz, then use the same continuation beam to prove the continuous
# 120 Hz route before resampling it to the ordinary 240 Hz IK bake lattice.
# Both refined torso-space paths are audited again between serialized keys.
COUPLED_PATH_RATE_BY_CLIP = {
    "c2d2": 240.0,
    "c2d3": 120.0,
    "c2d4": 120.0,
}
# The safe c2d2 hand trajectory is authored at 480 Hz, but coupled shoulder /
# forearm SLERP on a clean sparse-arm export still misses that trajectory
# between adjacent 960 Hz keys.  Resample the immutable pre-coupled arm curves
# and solve the same path at 1,920 Hz; the applied-pose gate then probes its
# midpoints at 3,840 Hz.  This changes only interpolation density, not the
# already clearance/torso/reach-audited shared hand path.
COUPLED_APPLY_RATE_BY_CLIP = {"c2d2": 1920.0}
COUPLED_PLAN_RATE_BY_CLIP = {
    "c2d2": 20.0,
    "c2d3": 30.0,
    "c2d4": 30.0,
}
COUPLED_GRIP_DRIFT_LIMIT_BY_CLIP = {
    # Malak's authored c2d1 guard opens the transferred two-hand grip by
    # 14.0 mm after the Ithorian limb-length solve. Keep a tight, clip-local
    # 15 mm ceiling instead of rejecting the donor's intended silhouette.
    "c2d1": 0.015,
    "c2d2": 0.0125,
    "c2d3": 0.0135,
}
COMBAT_HEAD_POSTURE_NODES = (
    "neckbase_g",
    "neck_g",
    "neckupr_g",
    "neckupr02_g",
    "neckupr03_g",
    "head_g",
)
ARM_POSITION_GOAL_NODES = tuple(
    f"{side}{role}_g"
    for side in ("r", "l")
    for role in ("bicep", "forearm", "hand")
)

# T2570: all-animation visual proof exposed additional ready/draw styles where
# the Ithorian's long arms cross the robe.  Keep arm ownership independent from
# head posture: g5 needs limb-length compensation but its eyes already face
# forward, while g3/g4/g8 need head posture without an arm rewrite.
READY_DRAW_ARM_POSITION_GOAL_CLIPS = {
    "g1r1", "g1w1",
    "g5r1", "g5w1",
    "g7r1", "g7w1",
    "g9r1", "g9w1",
}
# Malak's c2d2/c2d3/c2d4 guards already clear the corrected Ithorian head by
# 0.163/0.133/0.373 m respectively. The legacy coupled Set-2 planner does not
# converge for c2d2 because it searches for an unnecessary replacement path.
# Preserve those authored arm tracks and re-prove their serialized clearance
# below. c2d1 and c2d5 do intersect the head and remain in the coupled solver.
MALAK_DIRECT_SAFE_DEFEND_CLIPS = {"c2d2", "c2d3", "c2d4"}
MALAK_POST_POLICY_ARM_EXCLUSIONS = {"g1z1"}
MALAK_COMBAT_RUNTIME_CLIPS = (
    set(MALAK_COMBAT_SLOT_SOURCES) | set(COMBAT_ALIAS_SOURCES)
)
# Measured against the serialized Ithorian head surface at 120 Hz after the
# neck-posture solve. These Malak clips fall below the 0.12 m blade/head floor
# and therefore use the proven one-hand translation planner. Safe combat clips
# retain Malak's authored arm path unchanged.
MALAK_SABER_SURFACE_GOAL_CLIPS = {
    "c2a1", "c2a2", "c2a3", "c2a5", "c2a6",
    "c2n1", "c2n2",
    "c2p1", "c2p2", "c2p3", "c2p5",
    "f2a1", "f2a2", "f2a4",
    "f2d1", "f2d2", "f2d3",
    "f2p1", "f2p2", "f2p3",
    "g0a1", "g0a2", "g2w1",
}
ARM_POSITION_GOAL_CLIPS = (
    set(BASE_ARM_POSITION_GOAL_CLIPS)
    | READY_DRAW_ARM_POSITION_GOAL_CLIPS
    | MALAK_COMBAT_RUNTIME_CLIPS
) - MALAK_DIRECT_SAFE_DEFEND_CLIPS - MALAK_POST_POLICY_ARM_EXCLUSIONS

# T2569/T2570: humanoid combat neck rotations fold the long Ithorian neck
# chain downward, leaving the head scrunched into the chest and the eyes pitched
# at the floor.  Full-duration clips get the target-native six-node posture
# before arm IK.  Partial parry/get-up policies are applied in a second phase.
READY_DRAW_HEAD_POSTURE_CLIPS = {
    "c2n1", "c2n2", "c4n1", "c4n2",
    "creadyr", "g2r1", "g2w1",
    "g1r1", "g1w1",
    "g3r1", "g3w1",
    "g4r1", "g4w1",
    "g7r1", "g7w1",
    "g8r1",
    "g9r1", "g9w1",
}
COMBAT_HEAD_POSTURE_CLIPS = (
    set(BASE_ARM_POSITION_GOAL_CLIPS)
    | READY_DRAW_HEAD_POSTURE_CLIPS
    | MALAK_COMBAT_RUNTIME_CLIPS
)

# Set 4 is predominantly a one-handed saber vocabulary.  Its target arm tracks
# are baked at 60 Hz so the long Ithorian forearm cannot interpolate back
# through the robe or skull between the six sparse visual-review fractions.
# The right-hand blade is moved only as far forward as needed; the left hand,
# torso, authored root motion, and target-native upright neck remain untouched.
SET4_ARM_BAKE_RATE = 60.0
# A small number of clips cross a collision boundary between ordinary 60 Hz
# keys even though both endpoints are safe.  Serialize those equivalence
# classes at the same 120 Hz rate used by the shipped readback gate so every
# audited sample is an exact IK solve rather than an unsafe quaternion
# midpoint.  The source, c2 target, and any aliases share the selected rate.
SET4_ARM_BAKE_RATE_BY_SOURCE = {
    "c2a1": 120.0,
    "c2a3": 120.0,
    "c2p2": 120.0,
    "f2a1": 120.0,
    "f2d1": 120.0,
    "f2d2": 120.0,
    "f2p1": 120.0,
    "f2p2": 120.0,
    "f4a4": 120.0,
    "g4a1": 120.0,
}
MALAK_DIRECT_GREEDY_SABER_SOURCES = {
    "c2a1", "c2a3", "c2p2", "f2a1",
    "f2d1", "f2d2", "f2p1", "f2p2",
}
MALAK_RIGHT_ARM_ONLY_SURFACE_SOURCES = {"c2p1"}
SET4_SABER_SURFACE_GOAL_CLEARANCE = 0.15
SET4_SABER_FORWARD_SEARCH_LIMIT = 0.75
SET4_SABER_FORWARD_SEARCH_STEP = 0.015
SET4_SABER_MAX_CORRECTION_STEP = 0.06

# Fire-and-forget parries leave and return to their ready pose.  Correct only
# the ready-like edges so the authored middle of the parry remains intact.
PARRY_HEAD_REFERENCE_CLIPS = {
    "g2g1": "g2r1",
    "g1g1": "g1r1",
    "g3g1": "g3r1",
    "g4g1": "g4r1",
    "g7g1": "g7r1",
    "g8g1": "g8r1",
    "g9g1": "g9r1",
}

# Draw transitions must serialize into the exact corrected ready pose.  Scopes
# are deliberately per family: g3/g4 are posture-only, g5 is arm-only, and
# g1/g7/g9 need both corrections.
READY_ENDPOINT_MATCH_CLIPS = {
    "g2w1": ("g2r1", ("head",)),
    "g1w1": ("g1r1", ("head", "arms")),
    "g3w1": ("g3r1", ("head",)),
    "g4w1": ("g4r1", ("head",)),
    "g5w1": ("g5r1", ("arms",)),
    "g7w1": ("g7r1", ("head", "arms")),
    "g9w1": ("g9r1", ("head", "arms")),
}

# g1z1 is a prone-to-standing get-up.  Its early contact motion must remain
# authored; only the settled tail blends into the corrected g1 ready pose.
LATE_READY_BLEND_CLIPS = {
    "g1z1": {
        "reference": "g1r1",
        "start_fraction": 0.65,
        "clearance_fraction": 0.70,
        "full_fraction": 0.90,
        "scopes": ("head", "arms"),
    },
}

# c2a1's humanoid follow-through crosses the Ithorian eye line while both long
# arms are already at full reach.  A positional push only projects back onto
# that same reach sphere, so briefly blend the target's six arm owners toward
# c2a1's own clean endpoint guard instead.  The authored attack and final guard
# remain exact outside this narrow window.
TRANSIENT_CLEARANCE_POSE_CLIPS = {}
# Saber attachment hooks: the creature rig has no rhand/lhand dummies, so an
# equipped lightsaber would never render.  Local transforms copied from
# S_Male02 (parent bones rhand_g/lhand_g are shared with the Ithorian).
HAND_HOOKS = (
    ("rhand", "rhand_g", (-0.0317, -0.0118, -0.0854), (-0.6724, 0.0086, -0.0256, 0.7397)),
    ("lhand", "lhand_g", (0.0358, -0.0093, -0.075), (-0.7104, -0.0151, -0.0141, 0.7035)),
)
# Visible w_lghtsbr_002 blade centerline in the BAS-attached weapon-root frame.
# The red plane half-width is 0.102681m, so a 0.12m centerline/head-surface
# gate retains a small visible margin around the glow geometry.
RIGHT_SABER_CENTERLINE_LOCAL = (
    (0.0, 0.0, 0.0775029106),
    (0.0, 0.0, 1.1017320106),
)
RIGHT_SABER_HEAD_CLEARANCE_MIN = 0.12
# UTC donors: the actual Korriban Sith Academy Dark Jedi encounters
# (faction 1 hostile, red Dark Jedi saber g_w_drkjdisbr001, 3 force powers,
# CR 4) — extracted from korr_m35aa_s.rim per variant below.
KORRIBAN_RIM = pathlib.Path(K1) / "modules" / "korr_m35aa_s.rim"
APPEARANCE_TEMPLATE_ROW = 72          # Alien_Ithorian_01 (racetex empty)
LORUM_MODELTYPE = "F"                 # external rhand weapon attachment path

VARIANTS = [
    {
        "resref": "c_ithlord",
        "utc": "sithlord01",
        "display": "Lorum Ipsat",
        "label": "Alien_Ithorian_SithLord",
        "obj": SRC / "IthorianSithLord.obj",
        "tex": SRC / "IthorianSithLord_basecolor.jpg",
        "utc_donor": "kor35_sithteach1",
    },
]

LORUM_FEAT_IDS = (
    1, 4, 5, 6, 8, 11, 54, 21, 55, 28,
    93, 36, 39, 40, 41, 42, 43, 44, 45, 50,
)
LORUM_FORCE_POWER_IDS = (
    4, 8, 9, 13, 12, 15, 16, 23, 30, 43, 45, 49, 50,
)
# K1's uniquely named ``Malak's Lightsaber`` blueprint.  It resolves from
# templates.bif to the red ``w_lghtsbr_006`` model and is safe in RIGHT_HAND.
LORUM_RED_SABER = "g_w_lghtsbr06"
LORUM_ITHORIAN_SOUNDSET = 48


def korriban_utc_bytes(resref: str) -> bytes:
    """Extract a UTC from the Korriban academy module RIM."""
    import struct as _struct
    data = KORRIBAN_RIM.read_bytes()
    assert data[:8] == b"RIM V1.0", KORRIBAN_RIM
    cnt, off = _struct.unpack_from("<II", data, 0x0C)
    for i in range(cnt):
        e = off + i * 32
        name = data[e:e + 16].split(b"\0")[0].decode("ascii", "replace")
        rt, _idx, roff, rsize = _struct.unpack_from("<IIII", data, e + 16)
        if rt == 2027 and name.lower() == resref.lower():
            return data[roff:roff + rsize]
    raise AssertionError(f"{resref} not in {KORRIBAN_RIM.name}")


def configure_lorum_utc(root, *, appearance_row: int, display_name: str) -> None:
    """Turn the stock level-8 Sith teacher into hostile Lorum Ipsat.

    The donor already owns the correct GFF list/struct types for its feats and
    13 mid-tier Force powers.  Mutate only identity, faction/alignment, voice,
    generic hostile spawn behavior, appearance, and the right-hand saber.
    """

    root["Appearance_Type"] = int(appearance_row)
    root["FactionID"] = 1
    root["GoodEvil"] = 10
    root["SoundSetFile"] = LORUM_ITHORIAN_SOUNDSET
    root["Tag"] = "sithlord01"

    template = root.fields["TemplateResRef"]
    template.value = type(template.value)("sithlord01")
    spawn = root.fields["ScriptSpawn"]
    spawn.value = type(spawn.value)("k_pkor_spn_buff")

    first_name = root.fields["FirstName"].value
    first_name.strref = -1
    first_name.strings.clear()
    first_name.set_text(str(display_name), first_name.LANG_ENGLISH)
    last_name_field = root.fields.get("LastName")
    if last_name_field is not None and hasattr(last_name_field.value, "strings"):
        last_name_field.value.strref = -1
        last_name_field.value.strings.clear()

    weapon_slots = []
    for item in root.fields["Equip_ItemList"].value:
        equipped = item.fields.get("EquippedRes")
        if equipped is None or int(getattr(item, "type_id", -1)) != 16:
            continue
        equipped.value = type(equipped.value)(LORUM_RED_SABER)
        weapon_slots.append(str(equipped.value).lower())
    assert weapon_slots == [LORUM_RED_SABER], weapon_slots

from src.core.assets.resource_manager import ResourceManager, RES_2DA, RES_UTC  # noqa: E402
from src.core.characters import headless_body_workflow as wf  # noqa: E402
from src.core.characters import character_builder as cb  # noqa: E402
from src.core.geometry import model_data as md  # noqa: E402
from src.core.templates.twoda import TwoDA  # noqa: E402
from src.formats.gff_reader import read_gff  # noqa: E402
from src.formats.gff_writer import write_gff  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from diag_rancor_seam_divergence import (  # noqa: E402
    effective_weights_by_name,
    weight_delta,
)
from diag_rancor_full_animation_audit import audit_model  # noqa: E402
from build_dathomir_rancor import twoda_to_binary_v2b  # noqa: E402

KOTOR_MAX_TEX = int(os.environ.get("ITH_MAX_TEX", "2048"))
# T2557 gate: max allowed separation growth (meters) between vertex pairs
# that are bind-proximal (<3cm) — layered shells must move together.
CROSS_SHELL_MAX_GROWTH = float(os.environ.get("ITH_MAX_SHELL_GROWTH", "0.35"))
# Native bones that T2555's connectivity-splitter bug orphaned; their survival
# is now a build gate.
NECK_CHAIN = {
    "neckupr_g", "neckupr02_g", "neckupr03_g", "head_g",
    "lclothflap_g", "rclothflap_g", "talkdummy",
}


def rebuild_lorum_utc_only(
    appearance_rows: dict[str, int] | None = None,
) -> list[dict[str, object]]:
    """Rebuild just Lorum's UTC without touching accepted MDL/MDX assets."""

    if appearance_rows is None:
        appearance_path = OUT / "appearance.2da"
        assert appearance_path.is_file(), appearance_path
        appearance = TwoDA.from_bytes(appearance_path.read_bytes())
        appearance_rows = {}
        for spec in VARIANTS:
            matches = [
                index for index in range(len(appearance))
                if str(appearance.get(index, "race") or "").lower()
                == spec["resref"]
            ]
            assert len(matches) == 1, (spec["resref"], matches)
            appearance_rows[spec["resref"]] = matches[0]

    results: list[dict[str, object]] = []
    for spec in VARIANTS:
        appearance_row = int(appearance_rows[spec["resref"]])
        gff = read_gff(korriban_utc_bytes(spec["utc_donor"]))
        root = gff.root
        configure_lorum_utc(
            root,
            appearance_row=appearance_row,
            display_name=spec["display"],
        )
        utc_bytes = write_gff(gff)
        check = read_gff(utc_bytes)
        assert check.root.fields["Appearance_Type"].value == appearance_row
        checked_name = check.root.fields["FirstName"].value
        assert checked_name.strref == -1, checked_name
        assert checked_name.english == spec["display"], checked_name
        assert int(check.root.fields["FactionID"].value) == 1
        assert int(check.root.fields["SoundSetFile"].value) == LORUM_ITHORIAN_SOUNDSET
        assert int(check.root.fields["GoodEvil"].value) == 10
        assert str(check.root.fields["ScriptSpawn"].value) == "k_pkor_spn_buff"
        assert float(check.root.fields["ChallengeRating"].value) == 8.0
        assert int(check.root.fields["MaxHitPoints"].value) == 68
        assert int(check.root.fields["ForcePoints"].value) == 64
        classes = check.root.fields["ClassList"].value
        assert len(classes) == 1
        assert (
            int(classes[0].fields["Class"].value),
            int(classes[0].fields["ClassLevel"].value),
        ) == (3, 8)
        powers = tuple(
            int(spell.fields["Spell"].value)
            for spell in classes[0].fields["KnownList0"].value
        )
        feats = tuple(
            int(feat.fields["Feat"].value)
            for feat in check.root.fields["FeatList"].value
        )
        assert powers == LORUM_FORCE_POWER_IDS, powers
        assert feats == LORUM_FEAT_IDS, feats
        equip = [
            str(item.fields["EquippedRes"].value)
            for item in check.root.fields["Equip_ItemList"].value
            if "EquippedRes" in item.fields
        ]
        assert LORUM_RED_SABER in [item.lower() for item in equip], equip
        destination = OUT / f"{spec['utc']}.utc"
        destination.write_bytes(utc_bytes)
        result = {
            "utc": spec["utc"],
            "appearance": appearance_row,
            "name": spec["display"],
            "saber": LORUM_RED_SABER,
            "powers": len(powers),
            "equipment": equip,
            "size": len(utc_bytes),
        }
        results.append(result)
        print(
            f"utc: {destination.name} appearance={appearance_row} "
            f"name='{spec['display']}' donor={spec['utc_donor']} "
            f"CR=8 level=8 powers={len(powers)} soundset=Ithorian "
            f"equip={equip}"
        )

    manifest_path = OUT / "sith_ithorians_package.json"
    if manifest_path.is_file():
        package_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        package_manifest.setdefault("lorum_utc", {})["saber"] = LORUM_RED_SABER
        manifest_path.write_text(
            json.dumps(package_manifest, indent=2),
            encoding="utf-8",
        )
    return results


def assert_hand_attachment_hook_contract(model) -> dict[str, tuple[int, ...]]:
    """Require retail-shaped static transform tracks on weapon hook dummies."""

    result: dict[str, tuple[int, ...]] = {}
    nodes = {
        str(node.name or "").strip().lower(): node
        for node in model.all_nodes()
    }
    for hook_name, parent_name, hook_pos, hook_rot in HAND_HOOKS:
        hook = nodes.get(hook_name)
        assert hook is not None, f"missing weapon attachment hook {hook_name}"
        assert str(getattr(hook.parent, "name", "") or "").lower() == parent_name
        controllers = {
            int(controller.get("type", controller.get("controller_type", 0)) or 0): controller
            for controller in (hook.controllers or [])
        }
        assert {8, 20} <= set(controllers), (hook_name, sorted(controllers))
        position = controllers[8]
        orientation = controllers[20]
        assert [float(value) for value in position.get("times", [])] == [0.0]
        assert [float(value) for value in orientation.get("times", [])] == [0.0]
        assert int(position.get("columns", 0) or 0) == 3
        assert int(orientation.get("columns", 0) or 0) == 4
        position_value = tuple(float(value) for value in position["values"][0])
        orientation_value = tuple(float(value) for value in orientation["values"][0])
        assert all(abs(a - b) <= 1.0e-5 for a, b in zip(position_value, hook_pos))
        assert all(abs(a - b) <= 1.0e-5 for a, b in zip(orientation_value, hook_rot))
        result[hook_name] = tuple(sorted(controllers))
    return result


def weld_mesh_node(node, pos_tol=1.0e-5, uv_tol=1.0e-4):
    """Lossless weld of coincident (pos+uv+normal) vertices (T2543)."""
    verts = list(getattr(node, "vertices", []) or [])
    faces = list(getattr(node, "faces", []) or [])
    if not verts or not faces:
        return 0, 0
    uvs = list(getattr(node, "uvs", []) or [])
    normals = list(getattr(node, "normals", []) or [])
    has_uv = len(uvs) == len(verts)
    has_nrm = len(normals) == len(verts)

    def key(i):
        # T2566: weld on position+UV ONLY.  DCC re-exports split normals per
        # face corner (the user's edited OBJ ballooned 3520 -> 9834 verts,
        # 311 -> 3158 shells), which breaks KOTOR's per-node vertex budget
        # and the shell-regularization tuning.  Merging across normal splits
        # keeps the first normal per position (soft shading), matching the
        # original clean export's density.
        v = verts[i]
        k = (round(v[0] / pos_tol), round(v[1] / pos_tol), round(v[2] / pos_tol))
        if has_uv:
            u = uvs[i]
            k += (round(u[0] / uv_tol), round(u[1] / uv_tol))
        return k

    remap = {}
    new_v, new_uv, new_nrm = [], [], []
    old_to_new = [0] * len(verts)
    for i in range(len(verts)):
        k = key(i)
        j = remap.get(k)
        if j is None:
            j = len(new_v)
            remap[k] = j
            new_v.append(verts[i])
            if has_uv:
                new_uv.append(uvs[i])
            if has_nrm:
                new_nrm.append(normals[i])
        old_to_new[i] = j
    new_faces = []
    for f in faces:
        a, b, cc = old_to_new[int(f[0])], old_to_new[int(f[1])], old_to_new[int(f[2])]
        if a != b and b != cc and a != cc:
            new_faces.append((a, b, cc))
    before = len(verts)
    node.vertices = new_v
    node.faces = new_faces
    if has_uv:
        node.uvs = new_uv
    if has_nrm:
        node.normals = new_nrm
    if getattr(node, "skin_data", None):
        node.skin_data = []
    return before, len(new_v)


def _quat_mul_xyzw(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def _quat_inv_xyzw(q):
    x, y, z, w = q
    n = x * x + y * y + z * z + w * w
    if n <= 1.0e-12:
        return (0.0, 0.0, 0.0, 1.0)
    return (-x / n, -y / n, -z / n, w / n)


def _quat_norm_xyzw(q):
    import math as _math
    n = _math.sqrt(sum(c * c for c in q))
    if n <= 1.0e-12:
        return (0.0, 0.0, 0.0, 1.0)
    return tuple(c / n for c in q)


def _rest_world_rotations(model):
    """name(lower) -> world rest rotation (xyzw) composed up the parent chain."""
    out = {}

    def walk(node, parent_q):
        q = _quat_norm_xyzw(_quat_mul_xyzw(parent_q, tuple(
            float(c) for c in (node.rotation or (0, 0, 0, 1))[:4])))
        name = str(node.name or "").strip().lower()
        if name:
            out[name] = q
        for child in node.children or []:
            walk(child, q)

    walk(model.root_node, (0.0, 0.0, 0.0, 1.0))
    return out


def retarget_clip_orientations(anim, source_model, src_clip_name, rigged):
    """World-space orientation retarget (T2564).

    Orientation keys are ABSOLUTE parent-local rotations, so a raw copy only
    looks right where the target's rest orientation matches the source rig's.
    The Ithorian's arm rests differ from the humanoid rig — raw-copied clips
    point the right arm straight up (flagpole) where the Dark Jedi holds a
    bent-elbow saber guard, and the VANILLA Ithorian shows the identical
    artifact when force-fed g2r1, proving it is rest-frame mismatch and not a
    bake bug.  For every keyed bone shared by both rigs:

        C(b)        = inv(W_src_rest(b)) * W_ith_rest(b)
        W_des(t,b)  = W_src(t,b) * C(b)
        local(t,b)  = inv(W_des(t, parent_ith(b))) * W_des(t,b)

    which preserves the source clip's WORLD-space motion while landing every
    bone in the Ithorian's own rest frame.  Position deltas pass through
    (both rigs are anim_scale 1.0).
    """
    from src.core.animation.animation_engine import evaluate_aurora_animation_pose

    CTRL_ORIENTATION = 20
    src_clip = next(
        a for a in source_model.animations
        if str(a.name or "").lower() == src_clip_name.lower()
    )
    src_rest = _rest_world_rotations(source_model)
    ith_rest = _rest_world_rotations(rigged)
    ith_parent = {}
    for node in rigged.all_nodes():
        name = str(node.name or "").strip().lower()
        parent = getattr(node, "parent", None)
        if name and parent is not None:
            ith_parent[name] = str(parent.name or "").strip().lower()

    correction = {
        name: _quat_norm_xyzw(_quat_mul_xyzw(_quat_inv_xyzw(src_rest[name]), ith_rest[name]))
        for name in ith_rest
        if name in src_rest
    }

    pose_cache = {}

    def src_world(t, name):
        pose = pose_cache.get(t)
        if pose is None:
            pose = evaluate_aurora_animation_pose(source_model, src_clip, t)
            pose_cache[t] = pose
        for raw, entry in pose.world_transforms_by_node.items():
            if str(raw).strip().lower() == name:
                return tuple(float(c) for c in entry.rotation[:4])
        return None

    def desired_world(t, name):
        if name in correction:
            w = src_world(t, name)
            if w is not None:
                return _quat_norm_xyzw(_quat_mul_xyzw(w, correction[name]))
        return ith_rest.get(name)   # unkeyed / target-only bones hold rest

    converted = 0
    for anim_node in anim.nodes:
        name = str(anim_node.name or "").strip().lower()
        if name not in correction or name not in ith_parent:
            continue
        parent_name = ith_parent[name]
        for ctrl in anim_node.controllers or []:
            if ctrl.get("type") != CTRL_ORIENTATION:
                continue
            times = list(ctrl.get("times") or [])
            new_values = []
            for t in times:
                t = float(t)
                w_des = desired_world(t, name)
                w_par = desired_world(t, parent_name)
                local = _quat_norm_xyzw(
                    _quat_mul_xyzw(_quat_inv_xyzw(w_par), w_des))
                new_values.append(list(local))
            ctrl["values"] = new_values
            converted += 1
    return converted


def _quat_rotate_vec_xyzw(q, v):
    x, y, z, w = q
    vx, vy, vz = v
    # q * v * q^-1 (unit quat)
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    )


def _quat_between_vecs(u, v):
    import math as _math
    ux, uy, uz = u
    vx, vy, vz = v
    nu = _math.sqrt(ux * ux + uy * uy + uz * uz)
    nv = _math.sqrt(vx * vx + vy * vy + vz * vz)
    if nu < 1e-9 or nv < 1e-9:
        return (0.0, 0.0, 0.0, 1.0)
    ux, uy, uz = ux / nu, uy / nu, uz / nu
    vx, vy, vz = vx / nv, vy / nv, vz / nv
    cx, cy, cz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    d = max(-1.0, min(1.0, ux * vx + uy * vy + uz * vz))
    if d > 0.999999:
        return (0.0, 0.0, 0.0, 1.0)
    if d < -0.999999:
        ax, ay, az = (1.0, 0.0, 0.0) if abs(ux) < 0.9 else (0.0, 1.0, 0.0)
        cx, cy, cz = uy * az - uz * ay, uz * ax - ux * az, ux * ay - uy * ax
        return _quat_norm_xyzw((cx, cy, cz, 0.0))
    s = _math.sqrt((1.0 + d) * 2.0)
    return _quat_norm_xyzw((cx / s, cy / s, cz / s, s * 0.5))


def _quat_slerp_xyzw(a, b, factor):
    """Shortest-path quaternion interpolation in the MDL XYZW convention."""
    import math as _math

    q0 = _quat_norm_xyzw(tuple(float(c) for c in a[:4]))
    q1 = _quat_norm_xyzw(tuple(float(c) for c in b[:4]))
    dot = sum(x * y for x, y in zip(q0, q1))
    if dot < 0.0:
        q1 = tuple(-c for c in q1)
        dot = -dot
    dot = max(-1.0, min(1.0, dot))
    f = max(0.0, min(1.0, float(factor)))
    if dot > 0.9995:
        return _quat_norm_xyzw(tuple(
            (1.0 - f) * x + f * y for x, y in zip(q0, q1)))
    theta = _math.acos(dot)
    sin_theta = _math.sin(theta)
    if abs(sin_theta) <= 1.0e-9:
        return q0
    w0 = _math.sin((1.0 - f) * theta) / sin_theta
    w1 = _math.sin(f * theta) / sin_theta
    return _quat_norm_xyzw(tuple(w0 * x + w1 * y for x, y in zip(q0, q1)))


def _clean_animation_times(values, length, *, merge_epsilon=1.0e-4):
    """Clamp, float32-canonicalize, sort, and epsilon-merge key times.

    T2567's rounded 30 Hz keys could serialize onto the same float32 time as
    an original key and could also land just beyond ``animation.length``.
    The IK pass deliberately produces a strict, writer-stable time sequence.
    """
    cleaned = []
    length = max(0.0, float(length))
    for raw in sorted(float(v) for v in values):
        t = max(0.0, min(length, raw))
        t = struct.unpack("<f", struct.pack("<f", t))[0]
        if t > length:
            t = length
        if cleaned and t - cleaned[-1] <= merge_epsilon:
            cleaned[-1] = t
        else:
            cleaned.append(t)
    return cleaned


def _sample_orientation_track(times, values, sample_time, rest_rotation):
    """Sample one decoded orientation controller without mutating it."""
    import bisect as _bisect

    pairs = []
    for raw_t, raw_q in zip(times or [], values or []):
        if len(raw_q) >= 4:
            pairs.append((float(raw_t), tuple(float(c) for c in raw_q[:4])))
    pairs.sort(key=lambda row: row[0])
    if not pairs:
        return _quat_norm_xyzw(tuple(float(c) for c in rest_rotation[:4]))
    # Prefer the last value when malformed input carries duplicate times.
    unique = []
    for t, q in pairs:
        if unique and abs(t - unique[-1][0]) <= 1.0e-7:
            unique[-1] = (t, q)
        else:
            unique.append((t, q))
    ts = [row[0] for row in unique]
    t = float(sample_time)
    if t <= ts[0]:
        return _quat_norm_xyzw(unique[0][1])
    if t >= ts[-1]:
        return _quat_norm_xyzw(unique[-1][1])
    index = _bisect.bisect_right(ts, t) - 1
    t0, q0 = unique[index]
    t1, q1 = unique[index + 1]
    factor = (t - t0) / max(1.0e-9, t1 - t0)
    return _quat_slerp_xyzw(q0, q1, factor)


def _orientation_controller(anim_node):
    return next(
        (ctrl for ctrl in (anim_node.controllers or []) if ctrl.get("type") == 20),
        None,
    )


def _ensure_arm_orientation_track(anim, rigged, node_name, solve_times):
    """Create/densify one absolute parent-local orientation controller."""
    key = str(node_name).lower()
    anim_by_name = {
        str(node.name or "").strip().lower(): node for node in (anim.nodes or [])
    }
    rig_by_name = {
        str(node.name or "").strip().lower(): node for node in rigged.all_nodes()
    }
    rig_node = rig_by_name.get(key)
    if rig_node is None:
        raise AssertionError(f"target orientation node {node_name} missing")
    anim_node = anim_by_name.get(key)
    if anim_node is None:
        parent_anim = None
        walker = rig_node.parent
        while walker is not None and parent_anim is None:
            parent_anim = anim_by_name.get(str(walker.name or "").strip().lower())
            walker = walker.parent
        if parent_anim is None:
            raise AssertionError(f"no animation ancestor for {node_name} in {anim.name}")
        anim_node = md.ModelNode(name=str(rig_node.name))
        anim_node.parent = parent_anim
        parent_anim.children = list(parent_anim.children or []) + [anim_node]
        anim.nodes = list(anim.nodes or []) + [anim_node]

    ctrl = _orientation_controller(anim_node)
    rest_q = tuple(float(c) for c in (rig_node.rotation or (0, 0, 0, 1))[:4])
    if ctrl is None:
        ctrl = {
            "type": 20,
            "name": "orientation",
            "times": [],
            "values": [],
        }
        anim_node.controllers = list(anim_node.controllers or []) + [ctrl]
    old_times = list(ctrl.get("times") or [])
    old_values = list(ctrl.get("values") or [])
    seeded = [
        list(_sample_orientation_track(old_times, old_values, t, rest_q))
        for t in solve_times
    ]
    ctrl.update({
        "columns": 4,
        "binary_column_count": 4,
        "binary_unknown0": 28,
        "binary_unknown1": [0, 0, 0],
        "times": [float(t) for t in solve_times],
        "values": seeded,
    })
    from src.core.animation.animation_engine import mark_controller_times_sorted_for_sampling
    assert mark_controller_times_sorted_for_sampling(ctrl)
    # The binary writer prefers retained packed words when bincols==2.  These
    # keys are new XYZW values and must never inherit stale compression data.
    for stale in (
        "binary_compressed_quaternion_words",
        "binary_bezier_data",
        "binary_raw_data",
    ):
        ctrl.pop(stale, None)
    return ctrl


def _clip_by_name(model, clip_name):
    return next(
        (
            anim for anim in (model.animations or [])
            if str(anim.name or "").strip().lower() == str(clip_name).lower()
        ),
        None,
    )


def _animation_payload_signature(animation):
    """Return the serialized animation contract excluding only its slot name."""

    return (
        float(getattr(animation, "length", 0.0) or 0.0),
        float(getattr(animation, "transition_time", 0.0) or 0.0),
        str(getattr(animation, "anim_root", "") or ""),
        tuple(
            (float(event.time), str(event.name))
            for event in (animation.events or [])
        ),
        tuple(
            (
                str(getattr(node, "name", "") or ""),
                str(getattr(getattr(node, "parent", None), "name", "") or ""),
                int(getattr(node, "flags", 0) or 0),
                tuple(float(value) for value in (getattr(node, "position", ()) or ())),
                tuple(float(value) for value in (getattr(node, "rotation", ()) or ())),
                tuple(getattr(node, "controllers", ()) or ()),
            )
            for node in (animation.nodes or [])
        ),
    )


def install_modeltype_f_native_state_aliases(model):
    """Mirror stock Ithorian pause/death motion into modeltype-F slot names."""

    import copy

    animations = list(model.animations or [])
    index_by_name = {
        str(animation.name or "").strip().lower(): index
        for index, animation in enumerate(animations)
    }
    assert len(index_by_name) == len(animations), "duplicate animation names"

    report = {}
    for target_name, source_name in MODELTYPE_F_NATIVE_STATE_ALIASES.items():
        assert target_name in index_by_name, f"missing modeltype-F slot {target_name}"
        assert source_name in index_by_name, f"missing native Ithorian slot {source_name}"
        target_index = index_by_name[target_name]
        source = animations[index_by_name[source_name]]
        alias = copy.deepcopy(source)
        alias.name = str(animations[target_index].name or target_name)
        animations[target_index] = alias
        assert _animation_payload_signature(alias) == _animation_payload_signature(source)
        report[target_name] = {
            "source": source_name,
            "length": float(getattr(alias, "length", 0.0) or 0.0),
            "node_count": len(alias.nodes or []),
        }

    model.animations = animations
    return report


def _upright_head_posture_locals(rigged):
    """Return target-native upright local rotations for the Ithorian neck chain."""
    from src.core.animation.animation_engine import evaluate_aurora_animation_pose

    for clip_name in ("cpause1", "tlknorm", "cwalk"):
        ref_anim = _clip_by_name(rigged, clip_name)
        if ref_anim is None:
            continue
        ref_time = min(float(getattr(ref_anim, "length", 0.0) or 0.0), 1.43)
        pose = evaluate_aurora_animation_pose(rigged, ref_anim, ref_time)
        local = {
            str(name).strip().lower(): transform
            for name, transform in pose.local_transforms_by_node.items()
        }
        result = {}
        for node_name in COMBAT_HEAD_POSTURE_NODES:
            transform = local.get(node_name)
            if transform is None:
                break
            result[node_name] = _quat_norm_xyzw(
                tuple(float(c) for c in transform.rotation[:4]))
        if len(result) == len(COMBAT_HEAD_POSTURE_NODES):
            return result, clip_name, ref_time
    raise AssertionError("no native upright Ithorian neck posture clip found")


def _head_posture_solve_times(anim, upright_locals):
    import math as _math

    length = max(0.0, float(getattr(anim, "length", 0.0) or 0.0))
    times = [0.0, length]
    names = set(upright_locals)
    for node in anim.nodes or []:
        if str(node.name or "").strip().lower() not in names:
            continue
        for ctrl in node.controllers or []:
            times.extend(float(t) for t in (ctrl.get("times") or []))
    for index in range(int(_math.floor(length * 30.0)) + 1):
        times.append(index / 30.0)
    return _clean_animation_times(times, length)


def _policy_orientation_nodes(scopes):
    """Resolve named correction scopes to their exact animation-node owners."""
    result = []
    for scope in scopes:
        if scope == "head":
            candidates = COMBAT_HEAD_POSTURE_NODES
        elif scope == "arms":
            candidates = ARM_POSITION_GOAL_NODES
        else:
            raise AssertionError(f"unknown pose correction scope {scope!r}")
        for node_name in candidates:
            if node_name not in result:
                result.append(node_name)
    return tuple(result)


def _smoothstep(value, start, end):
    """C1-continuous scalar ramp used by partial pose corrections."""
    if end <= start:
        return float(value >= end)
    factor = max(0.0, min(1.0, (float(value) - start) / (end - start)))
    return factor * factor * (3.0 - 2.0 * factor)


def _transient_hold_weight(
        fraction, start_fraction, full_start_fraction,
        full_end_fraction, end_fraction):
    """C1 rise/hold/fall window for a temporary collision-free pose."""
    rise = _smoothstep(fraction, start_fraction, full_start_fraction)
    fall = 1.0 - _smoothstep(fraction, full_end_fraction, end_fraction)
    return max(0.0, min(1.0, rise * fall))


def _parry_head_edge_weight(fraction):
    """Keep ready posture at parry edges while preserving the authored middle."""
    fraction = max(0.0, min(1.0, float(fraction)))
    if fraction <= 0.20:
        return 1.0
    if fraction < 0.40:
        return 1.0 - _smoothstep(fraction, 0.20, 0.40)
    if fraction <= 0.75:
        return 0.0
    if fraction < 0.95:
        return _smoothstep(fraction, 0.75, 0.95)
    return 1.0


def _orientation_blend_solve_times(anim, node_names, dense_ranges):
    """Return writer-stable key times, densely sampling only corrected windows."""
    import math as _math

    length = max(0.0, float(getattr(anim, "length", 0.0) or 0.0))
    names = {str(name).strip().lower() for name in node_names}
    times = [0.0, length]
    for node in anim.nodes or []:
        if str(node.name or "").strip().lower() not in names:
            continue
        ctrl = _orientation_controller(node)
        if ctrl is not None:
            times.extend(float(t) for t in (ctrl.get("times") or []))
    for start_fraction, end_fraction in dense_ranges:
        start_time = length * max(0.0, min(1.0, float(start_fraction)))
        end_time = length * max(0.0, min(1.0, float(end_fraction)))
        if end_time < start_time:
            start_time, end_time = end_time, start_time
        times.extend((start_time, end_time))
        first = int(_math.floor(start_time * 30.0))
        last = int(_math.ceil(end_time * 30.0))
        for index in range(first, last + 1):
            candidate = index / 30.0
            if start_time <= candidate <= end_time:
                times.append(candidate)
    return _clean_animation_times(times, length)


def blend_animation_orientations_to_reference(
        anim, rigged, reference_anim, node_names, weight_fn, *,
        dense_ranges=(), reference_fraction=0.0):
    """Blend selected absolute parent-local tracks toward a corrected reference.

    Tracks outside the active weight windows retain samples from the serialized
    animation.  Quaternion interpolation is shortest-path and the final tracks
    are sign-continuous, matching the T2568 writer contract.
    """
    from src.core.animation.animation_engine import evaluate_aurora_animation_pose

    node_names = tuple(str(name).strip().lower() for name in node_names)
    solve_times = _orientation_blend_solve_times(anim, node_names, dense_ranges)
    tracks = {
        node_name: _ensure_arm_orientation_track(anim, rigged, node_name, solve_times)
        for node_name in node_names
    }
    original_values = {
        node_name: [tuple(float(c) for c in value[:4]) for value in ctrl["values"]]
        for node_name, ctrl in tracks.items()
    }
    reference_length = max(
        0.0, float(getattr(reference_anim, "length", 0.0) or 0.0))
    reference_time = reference_length * max(
        0.0, min(1.0, float(reference_fraction)))
    reference_pose = evaluate_aurora_animation_pose(
        rigged, reference_anim, reference_time)
    reference_local = {
        str(name).strip().lower(): transform
        for name, transform in reference_pose.local_transforms_by_node.items()
    }
    missing = [node_name for node_name in node_names if node_name not in reference_local]
    if missing:
        raise AssertionError(
            f"{anim.name}: reference {reference_anim.name} missing nodes {missing}")
    reference_rotations = {
        node_name: _quat_norm_xyzw(tuple(
            float(c) for c in reference_local[node_name].rotation[:4]))
        for node_name in node_names
    }

    length = max(0.0, float(getattr(anim, "length", 0.0) or 0.0))
    active_keys = 0
    for key_index, time_value in enumerate(solve_times):
        fraction = 1.0 if length <= 1.0e-9 else float(time_value) / length
        weight = max(0.0, min(1.0, float(weight_fn(fraction))))
        active_keys += int(weight > 1.0e-8) * len(node_names)
        for node_name, ctrl in tracks.items():
            ctrl["values"][key_index] = list(_quat_slerp_xyzw(
                original_values[node_name][key_index],
                reference_rotations[node_name],
                weight,
            ))
    for ctrl in tracks.values():
        _restore_orientation_continuity(ctrl)
    return {
        "solve_times": len(solve_times),
        "keys": len(solve_times) * len(node_names),
        "active_keys": active_keys,
        "nodes": node_names,
        "reference_fraction": float(reference_fraction),
    }


def retarget_combat_head_posture(anim, rigged, upright_locals):
    """Bake an upright target-native neck/head posture onto combat clips.

    This is intentionally target-space, not source-space: the desired result is
    the Ithorian's own long-neck posture standing tall, with eyes generally
    forward in torso space, while torso/root combat motion continues to drive
    the whole character.
    """
    solve_times = _head_posture_solve_times(anim, upright_locals)
    tracks = {
        node_name: _ensure_arm_orientation_track(anim, rigged, node_name, solve_times)
        for node_name in COMBAT_HEAD_POSTURE_NODES
    }
    keys = 0
    for node_name, ctrl in tracks.items():
        q = upright_locals[node_name]
        ctrl["values"] = [list(q) for _time in solve_times]
        _restore_orientation_continuity(ctrl)
        keys += len(solve_times)
    return {
        "solve_times": len(solve_times),
        "keys": keys,
    }


def audit_combat_head_posture(
        anim, rigged, *, start_fraction=0.0, end_fraction=1.0):
    """Measure head height and eye direction in animated torsoUpr_g space."""
    import math as _math
    from src.core.animation.animation_engine import evaluate_aurora_animation_pose

    length = max(0.0, float(getattr(anim, "length", 0.0) or 0.0))
    start_time = length * max(0.0, min(1.0, float(start_fraction)))
    end_time = length * max(0.0, min(1.0, float(end_fraction)))
    if end_time < start_time:
        start_time, end_time = end_time, start_time
    sample_times = [
        index / 30.0
        for index in range(
            int(_math.floor(start_time * 30.0)),
            int(_math.ceil(end_time * 30.0)) + 1,
        )
        if start_time <= index / 30.0 <= end_time
    ]
    sample_times = _clean_animation_times(
        sample_times + [start_time, end_time], length)
    min_head_z = 999.0
    min_head_y = 999.0
    min_forward_y = 999.0
    min_forward_z = 999.0
    max_abs_side = 0.0
    for time_value in sample_times:
        pose = evaluate_aurora_animation_pose(rigged, anim, time_value)
        world = _pose_world_by_name(pose)
        torso = world["torsoupr_g"]
        head = world["head_g"]
        hx, hy, hz = _point_in_frame(head.position, torso)
        head_forward_world = _quat_rotate_vec_xyzw(
            tuple(float(c) for c in head.rotation[:4]), (0.0, 1.0, 0.0))
        head_forward_torso = _quat_rotate_vec_xyzw(
            _quat_inv_xyzw(tuple(float(c) for c in torso.rotation[:4])),
            head_forward_world,
        )
        min_head_z = min(min_head_z, hz)
        min_head_y = min(min_head_y, hy)
        max_abs_side = max(max_abs_side, abs(hx))
        min_forward_y = min(min_forward_y, head_forward_torso[1])
        min_forward_z = min(min_forward_z, head_forward_torso[2])
    return {
        "samples": len(sample_times),
        "min_head_z": min_head_z,
        "min_head_y": min_head_y,
        "max_abs_side": max_abs_side,
        "min_forward_y": min_forward_y,
        "min_forward_z": min_forward_z,
    }


def _quat_angle_degrees_xyzw(a, b):
    """Return the sign-invariant angular distance between two rotations."""
    import math as _math

    q0 = _quat_norm_xyzw(tuple(float(c) for c in a[:4]))
    q1 = _quat_norm_xyzw(tuple(float(c) for c in b[:4]))
    dot = abs(sum(x * y for x, y in zip(q0, q1)))
    return _math.degrees(2.0 * _math.acos(max(-1.0, min(1.0, dot))))


def audit_orientation_reference_match(
        anim, reference_anim, rigged, node_names, sample_fractions, *,
        reference_fraction=0.0):
    """Measure serialized local-rotation seams against a corrected ready pose."""
    from src.core.animation.animation_engine import evaluate_aurora_animation_pose

    reference_length = max(
        0.0, float(getattr(reference_anim, "length", 0.0) or 0.0))
    reference_time = reference_length * max(
        0.0, min(1.0, float(reference_fraction)))
    reference_pose = evaluate_aurora_animation_pose(
        rigged, reference_anim, reference_time)
    reference_local = {
        str(name).strip().lower(): transform
        for name, transform in reference_pose.local_transforms_by_node.items()
    }
    node_names = tuple(str(name).strip().lower() for name in node_names)
    length = max(0.0, float(getattr(anim, "length", 0.0) or 0.0))
    max_angle = 0.0
    samples = 0
    for fraction in sample_fractions:
        time_value = length * max(0.0, min(1.0, float(fraction)))
        pose = evaluate_aurora_animation_pose(rigged, anim, time_value)
        local = {
            str(name).strip().lower(): transform
            for name, transform in pose.local_transforms_by_node.items()
        }
        for node_name in node_names:
            if node_name not in local or node_name not in reference_local:
                raise AssertionError(
                    f"{anim.name}: seam audit missing {node_name} against "
                    f"{reference_anim.name}")
            max_angle = max(max_angle, _quat_angle_degrees_xyzw(
                local[node_name].rotation, reference_local[node_name].rotation))
            samples += 1
    return {"samples": samples, "max_angle_degrees": max_angle}


def _restore_orientation_continuity(ctrl):
    values = []
    previous = None
    for raw in ctrl.get("values") or []:
        q = _quat_norm_xyzw(tuple(float(c) for c in raw[:4]))
        if previous is not None and sum(a * b for a, b in zip(previous, q)) < 0.0:
            q = tuple(-c for c in q)
        values.append(list(q))
        previous = q
    ctrl["values"] = values


def _pose_world_by_name(pose):
    return {
        str(name).strip().lower(): transform
        for name, transform in pose.world_transforms_by_node.items()
    }


def _point_in_frame(point, frame):
    rotation = tuple(float(c) for c in frame.rotation[:4])
    delta = tuple(float(a) - float(b) for a, b in zip(point, frame.position))
    return _quat_rotate_vec_xyzw(_quat_inv_xyzw(rotation), delta)


def _point_from_frame(point, frame):
    rotation = tuple(float(c) for c in frame.rotation[:4])
    offset = _quat_rotate_vec_xyzw(rotation, tuple(float(c) for c in point))
    return tuple(float(a) + float(b) for a, b in zip(frame.position, offset))


def _combat_hand_goal_body(
        source_world, target_world, side, *, apply_head_clearance=True):
    """Map the donor hand into animated target torsoUpr space.

    The source position is the actual Dark Jedi oracle.  A small target-only
    head clearance moves a high guard forward of the Ithorian's protruding
    skull; the torso capsule keeps mapped goals out of the wider robe/chest.
    """
    import math as _math

    source_torso = source_world["torsoupr_g"]
    target_torso = target_world["torsoupr_g"]
    source_hand = source_world[f"{side}hand_g"]
    gx, gy, gz = _point_in_frame(source_hand.position, source_torso)
    # Preserve the donor wind-up except for its single deepest back-swing;
    # the user's explicit contract is that a saber hand never parks behind
    # this creature's torso.  Margin keeps interpolation clear of the -0.33m
    # verification plane without flattening the attack arc.
    gy = max(gy, -0.30)

    target_head = target_world.get("head_g")
    if apply_head_clearance and target_head is not None:
        _hx, hy, hz = _point_in_frame(target_head.position, target_torso)
        if gz >= hz - 0.10:
            gy = max(gy, hy + 0.16)

    return _project_hand_goal_outside_torso((gx, gy, gz), side)


def _project_hand_goal_outside_torso(goal_body, side):
    """Project one torso-frame hand goal onto the arm-clearance volume."""
    import math as _math

    gx, gy, gz = (float(component) for component in goal_body)
    back_plane = -0.30
    capsule_center_y = -0.05
    capsule_radius = 0.405
    gy = max(gy, back_plane)
    radius = _math.hypot(gx, gy - capsule_center_y)
    if gy < 0.18 and radius < capsule_radius:
        if radius <= 1.0e-8:
            gx = capsule_radius if str(side).lower() == "r" else -capsule_radius
            gy = capsule_center_y
        else:
            scale = capsule_radius / radius
            gx *= scale
            gy = (gy - capsule_center_y) * scale + capsule_center_y
        # Radial projection can cross the back plane when the source goal is
        # behind and close to the torso centre (f4a4 at 26.7% exposed this).
        # Clamp the plane again and move sideways to the circle/plane
        # intersection, satisfying both constraints rather than alternating
        # between them.
        if gy < back_plane:
            gy = back_plane
            minimum_abs_x = _math.sqrt(max(
                0.0,
                capsule_radius * capsule_radius
                - (gy - capsule_center_y) * (gy - capsule_center_y),
            ))
            sign = 1.0 if gx >= 0.0 else -1.0
            if abs(gx) <= 1.0e-8:
                sign = 1.0 if str(side).lower() == "r" else -1.0
            gx = sign * max(abs(gx), minimum_abs_x)
    return (gx, gy, gz)


def blend_animation_arm_goals_to_reference(
        anim, rigged, reference_anim, *, start_fraction, clearance_fraction,
        full_fraction):
    """Blend a transition tail to a ready pose through safe torso-frame IK.

    The authored arm pose remains exact through ``start_fraction``.  Between
    that point and ``full_fraction`` the current hand and elbow-pole positions
    move toward the corrected ready pose in animated ``torsoUpr_g`` space.  The
    torso-capsule projection fades in by ``clearance_fraction`` so a get-up can
    leave its intentional body contact without a one-frame snap.  From
    ``full_fraction`` onward the exact reference locals are serialized for a
    zero-angle transition seam.
    """
    import math as _math
    from src.core.animation.animation_engine import evaluate_aurora_animation_pose
    from src.math.limb_ik import solve_two_bone_positions

    node_names = tuple(ARM_POSITION_GOAL_NODES)
    solve_times = _orientation_blend_solve_times(
        anim,
        node_names,
        (
            (start_fraction, clearance_fraction),
            (clearance_fraction, full_fraction),
            (full_fraction, 1.0),
        ),
    )
    tracks = {
        node_name: _ensure_arm_orientation_track(
            anim, rigged, node_name, solve_times)
        for node_name in node_names
    }
    rig_by_name = {
        str(node.name or "").strip().lower(): node for node in rigged.all_nodes()
    }

    reference_pose = evaluate_aurora_animation_pose(
        rigged, reference_anim, 0.0)
    reference_world = _pose_world_by_name(reference_pose)
    reference_local = {
        str(name).strip().lower(): transform
        for name, transform in reference_pose.local_transforms_by_node.items()
    }
    required_reference = {"torsoupr_g", *node_names}
    missing = sorted(
        name for name in required_reference
        if name not in reference_world or (
            name in node_names and name not in reference_local)
    )
    if missing:
        raise AssertionError(
            f"{anim.name}: reference {reference_anim.name} missing nodes {missing}")

    reference_torso = reference_world["torsoupr_g"]
    reference_torso_q = tuple(
        float(component) for component in reference_torso.rotation[:4])
    reference_local_q = {
        node_name: _quat_norm_xyzw(tuple(
            float(component)
            for component in reference_local[node_name].rotation[:4]))
        for node_name in node_names
    }
    reference_hand_body = {}
    reference_elbow_body = {}
    reference_hand_body_q = {}
    for side in ("r", "l"):
        reference_hand_body[side] = _point_in_frame(
            reference_world[f"{side}hand_g"].position, reference_torso)
        reference_elbow_body[side] = _point_in_frame(
            reference_world[f"{side}forearm_g"].position, reference_torso)
        reference_hand_world_q = tuple(
            float(component)
            for component in reference_world[f"{side}hand_g"].rotation[:4]
        )
        reference_hand_body_q[side] = _quat_norm_xyzw(_quat_mul_xyzw(
            _quat_inv_xyzw(reference_torso_q), reference_hand_world_q))

    length = max(0.0, float(getattr(anim, "length", 0.0) or 0.0))
    active_keys = 0
    projected = 0
    max_projection = 0.0
    max_landing_error = 0.0
    for key_index, time_value in enumerate(solve_times):
        fraction = 1.0 if length <= 1.0e-9 else float(time_value) / length
        weight = _smoothstep(fraction, start_fraction, full_fraction)
        if weight <= 1.0e-8:
            continue
        if weight >= 1.0 - 1.0e-8:
            for node_name in node_names:
                tracks[node_name]["values"][key_index] = list(
                    reference_local_q[node_name])
            active_keys += len(node_names)
            continue

        safety_weight = _smoothstep(
            fraction, start_fraction, clearance_fraction)
        for side in ("r", "l"):
            target_pose = evaluate_aurora_animation_pose(
                rigged, anim, time_value)
            target_world = _pose_world_by_name(target_pose)
            target_torso = target_world["torsoupr_g"]
            target_torso_q = tuple(
                float(component) for component in target_torso.rotation[:4])
            shoulder = target_world[f"{side}bicep_g"]
            elbow = target_world[f"{side}forearm_g"]
            hand = target_world[f"{side}hand_g"]
            original_hand_world_q = tuple(
                float(component) for component in hand.rotation[:4])

            current_hand_body = _point_in_frame(
                hand.position, target_torso)
            raw_goal_body = tuple(
                (1.0 - weight) * current + weight * ready
                for current, ready in zip(
                    current_hand_body, reference_hand_body[side])
            )
            safe_goal_body = _project_hand_goal_outside_torso(
                raw_goal_body, side)
            goal_body = tuple(
                (1.0 - safety_weight) * raw + safety_weight * safe
                for raw, safe in zip(raw_goal_body, safe_goal_body)
            )
            goal_world = _point_from_frame(goal_body, target_torso)

            current_elbow_body = _point_in_frame(
                elbow.position, target_torso)
            pole_body = tuple(
                (1.0 - weight) * current + weight * ready
                for current, ready in zip(
                    current_elbow_body, reference_elbow_body[side])
            )
            pole_world = _point_from_frame(pole_body, target_torso)
            solution = solve_two_bone_positions(
                shoulder.position,
                elbow.position,
                hand.position,
                goal_world,
                pole_world,
            )
            projected += int(not solution.reached)
            max_projection = max(max_projection, float(solution.residual))

            shoulder_delta = _quat_between_vecs(
                tuple(float(a) - float(b) for a, b in zip(
                    elbow.position, shoulder.position)),
                tuple(float(a) - float(b) for a, b in zip(
                    solution.elbow_position, shoulder.position)),
            )
            new_shoulder_world = _quat_norm_xyzw(_quat_mul_xyzw(
                shoulder_delta,
                tuple(float(component) for component in shoulder.rotation[:4]),
            ))
            shoulder_parent = rig_by_name[f"{side}bicep_g"].parent
            parent_world = target_world[
                str(shoulder_parent.name or "").strip().lower()]
            tracks[f"{side}bicep_g"]["values"][key_index] = list(
                _quat_norm_xyzw(_quat_mul_xyzw(
                    _quat_inv_xyzw(tuple(
                        float(component)
                        for component in parent_world.rotation[:4])),
                    new_shoulder_world,
                )))

            target_pose = evaluate_aurora_animation_pose(
                rigged, anim, time_value)
            target_world = _pose_world_by_name(target_pose)
            elbow = target_world[f"{side}forearm_g"]
            hand = target_world[f"{side}hand_g"]
            elbow_delta = _quat_between_vecs(
                tuple(float(a) - float(b) for a, b in zip(
                    hand.position, elbow.position)),
                tuple(float(a) - float(b) for a, b in zip(
                    solution.target_position, elbow.position)),
            )
            new_elbow_world = _quat_norm_xyzw(_quat_mul_xyzw(
                elbow_delta,
                tuple(float(component) for component in elbow.rotation[:4]),
            ))
            elbow_parent = rig_by_name[f"{side}forearm_g"].parent
            parent_world = target_world[
                str(elbow_parent.name or "").strip().lower()]
            tracks[f"{side}forearm_g"]["values"][key_index] = list(
                _quat_norm_xyzw(_quat_mul_xyzw(
                    _quat_inv_xyzw(tuple(
                        float(component)
                        for component in parent_world.rotation[:4])),
                    new_elbow_world,
                )))

            original_hand_body_q = _quat_norm_xyzw(_quat_mul_xyzw(
                _quat_inv_xyzw(target_torso_q), original_hand_world_q))
            desired_hand_body_q = _quat_slerp_xyzw(
                original_hand_body_q,
                reference_hand_body_q[side],
                weight,
            )
            desired_hand_world_q = _quat_norm_xyzw(_quat_mul_xyzw(
                target_torso_q, desired_hand_body_q))
            target_pose = evaluate_aurora_animation_pose(
                rigged, anim, time_value)
            target_world = _pose_world_by_name(target_pose)
            hand_parent = rig_by_name[f"{side}hand_g"].parent
            parent_world = target_world[
                str(hand_parent.name or "").strip().lower()]
            tracks[f"{side}hand_g"]["values"][key_index] = list(
                _quat_norm_xyzw(_quat_mul_xyzw(
                    _quat_inv_xyzw(tuple(
                        float(component)
                        for component in parent_world.rotation[:4])),
                    desired_hand_world_q,
                )))

            target_pose = evaluate_aurora_animation_pose(
                rigged, anim, time_value)
            solved_hand = _pose_world_by_name(
                target_pose)[f"{side}hand_g"]
            landing_error = _math.dist(
                solved_hand.position, solution.target_position)
            max_landing_error = max(max_landing_error, landing_error)
            if landing_error > 1.0e-4:
                raise AssertionError(
                    f"{anim.name} {side}hand transition IK miss at "
                    f"{time_value:.5f}: {landing_error:.6f}m")
            active_keys += 3

    for ctrl in tracks.values():
        _restore_orientation_continuity(ctrl)
    return {
        "solve_times": len(solve_times),
        "keys": len(solve_times) * len(node_names),
        "active_keys": active_keys,
        "nodes": node_names,
        "projected": projected,
        "max_projection": max_projection,
        "max_landing_error": max_landing_error,
    }


def _solve_with_lower_left_elbow(
        shoulder, elbow, hand, goal_world, pole_world, *,
        margin=LEFT_ELBOW_WRIST_MARGIN):
    """Select the smallest downward bend-pole blend that lowers the elbow."""
    import math as _math
    from src.math.limb_ik import solve_two_bone_positions

    def solve_at(weight):
        source_delta = tuple(
            float(a) - float(b) for a, b in zip(
                pole_world, shoulder.position))
        source_length = max(1.0, _math.sqrt(sum(
            component * component for component in source_delta)))
        down_delta = (0.0, 0.0, -source_length)
        blended_delta = tuple(
            (1.0 - float(weight)) * source + float(weight) * down
            for source, down in zip(source_delta, down_delta)
        )
        candidate_pole = tuple(
            float(origin) + float(delta)
            for origin, delta in zip(shoulder.position, blended_delta)
        )
        candidate_solution = solve_two_bone_positions(
            shoulder.position,
            elbow.position,
            hand.position,
            goal_world,
            candidate_pole,
        )
        gap = (
            float(candidate_solution.target_position[2])
            - float(candidate_solution.elbow_position[2])
        )
        return candidate_solution, candidate_pole, float(gap)

    base_solution, base_pole, base_gap = solve_at(0.0)
    if base_gap >= float(margin):
        return base_solution, base_pole, 0.0, base_gap

    lower_weight = 0.0
    upper_weight = None
    upper_result = None
    best_result = (base_solution, base_pole, base_gap)
    for index in range(1, 33):
        weight = float(index) / 32.0
        result = solve_at(weight)
        if result[2] > best_result[2]:
            best_result = result
        if result[2] >= float(margin):
            upper_weight = weight
            upper_result = result
            break
        lower_weight = weight
    if upper_weight is None or upper_result is None:
        pole_displacement = _math.dist(pole_world, best_result[1])
        return (
            best_result[0],
            best_result[1],
            float(pole_displacement),
            float(best_result[2]),
        )
    for _iteration in range(14):
        midpoint = 0.5 * (lower_weight + upper_weight)
        result = solve_at(midpoint)
        if result[2] >= float(margin):
            upper_weight = midpoint
            upper_result = result
        else:
            lower_weight = midpoint
    pole_displacement = _math.dist(pole_world, upper_result[1])
    return (
        upper_result[0],
        upper_result[1],
        float(pole_displacement),
        float(upper_result[2]),
    )


def _coupled_defend_translation_directions(clip_name=""):
    """Deterministic torso-space direction lattice for two-hand clearance."""
    import math as _math

    result = []
    seen = set()
    for elevation_degrees in (-60, -30, 0, 30, 60):
        elevation = _math.radians(float(elevation_degrees))
        horizontal = _math.cos(elevation)
        vertical = _math.sin(elevation)
        for azimuth_degrees in range(0, 360, 30):
            azimuth = _math.radians(float(azimuth_degrees))
            direction = (
                horizontal * _math.cos(azimuth),
                horizontal * _math.sin(azimuth),
                vertical,
            )
            # Never choose a strongly backward detour.  Small negative-Y arcs
            # remain available because some authored parries already hold the
            # hilt well forward and clear the skull most naturally to a side.
            if direction[1] < -0.55:
                continue
            key = tuple(round(float(component), 6) for component in direction)
            if key not in seen:
                seen.add(key)
                result.append(tuple(float(component) for component in direction))
    for direction in (
            (0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (-1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0), (0.0, 0.0, -1.0)):
        if direction not in result:
            result.append(direction)
    return tuple(result)


def _hand_body_outside_torso(point):
    """Use a serialization margin around the shipped hand/robe audit."""
    import math as _math

    x, y, _z = (float(component) for component in point)
    radius = _math.hypot(x, y + 0.05)
    return y >= -0.30 and not (y < 0.18 and radius < 0.405)


def _coupled_defend_frame_context(anim, rigged, time_value):
    """Measure one uncorrected defend pose in animated ``torsoUpr_g`` space."""
    import math as _math
    import numpy as np
    from src.core.animation.animation_engine import evaluate_aurora_animation_pose

    pose = evaluate_aurora_animation_pose(rigged, anim, float(time_value))
    world = _pose_world_by_name(pose)
    torso = world["torsoupr_g"]
    hand_body = {
        side: np.asarray(_point_in_frame(
            world[f"{side}hand_g"].position, torso), dtype=np.float64)
        for side in ("r", "l")
    }
    shoulder_body = {
        side: np.asarray(_point_in_frame(
            world[f"{side}bicep_g"].position, torso), dtype=np.float64)
        for side in ("r", "l")
    }
    reach = {}
    minimum_reach = {}
    for side in ("r", "l"):
        shoulder = world[f"{side}bicep_g"]
        elbow = world[f"{side}forearm_g"]
        hand = world[f"{side}hand_g"]
        upper = _math.dist(shoulder.position, elbow.position)
        lower = _math.dist(elbow.position, hand.position)
        reach[side] = float(upper + lower)
        minimum_reach[side] = float(abs(upper - lower))

    socket = world.get("rhand")
    if socket is None:
        raise AssertionError(f"{anim.name}: animated rhand socket missing")
    socket_q = tuple(float(component) for component in socket.rotation[:4])
    segment = []
    for local_point in RIGHT_SABER_CENTERLINE_LOCAL:
        point_world = tuple(
            float(a) + float(b) for a, b in zip(
                socket.position,
                _quat_rotate_vec_xyzw(socket_q, local_point),
            )
        )
        segment.append(np.asarray(
            _point_in_frame(point_world, torso), dtype=np.float64))
    return {
        "time": float(time_value),
        "hand_body": hand_body,
        "shoulder_body": shoulder_body,
        "reach": reach,
        "minimum_reach": minimum_reach,
        "segment": tuple(segment),
    }


def _coupled_defend_delta_status(context, delta, head_triangles_body):
    """Return exact reach, robe, and blade/head truth for one shared delta."""
    import numpy as np

    delta = np.asarray(delta, dtype=np.float64)
    torso_violations = 0
    reach_violations = 0
    max_reach_excess = 0.0
    max_reach_deficit = 0.0
    for side in ("r", "l"):
        candidate = context["hand_body"][side] + delta
        torso_violations += int(not _hand_body_outside_torso(candidate))
        distance = float(np.linalg.norm(
            candidate - context["shoulder_body"][side]))
        excess = max(0.0, distance - float(context["reach"][side]))
        deficit = max(
            0.0, float(context["minimum_reach"][side]) - distance)
        max_reach_excess = max(max_reach_excess, excess)
        max_reach_deficit = max(max_reach_deficit, deficit)
        reach_violations += int(excess > 1.0e-6 or deficit > 1.0e-6)
    if torso_violations or reach_violations:
        # The state is already unusable; avoid the much more expensive exact
        # segment/triangle query and report a conservative collision distance.
        clearance = 0.0
    else:
        segment = context["segment"]
        clearance = _segment_triangles_distance(
            segment[0] + delta,
            segment[1] + delta,
            head_triangles_body,
        )
    return {
        "clearance": float(clearance),
        "torso_violations": int(torso_violations),
        "reach_violations": int(reach_violations),
        "max_reach_excess": float(max_reach_excess),
        "max_reach_deficit": float(max_reach_deficit),
    }


def _plan_coupled_defend_deltas(
        anim, rigged, solve_times, head_triangles_body, *,
        clearance=SABER_SURFACE_GOAL_CLEARANCE):
    """Plan one continuous torso-space translation shared by both hands.

    Every state is inside the intersection of the two arm reach volumes and
    keeps both hands outside the robe capsule.  Dynamic programming selects a
    whole-clip path, so a locally shorter solution cannot switch branches and
    send the interpolated blade back through the head between keys.
    """
    import math as _math
    import numpy as np
    from src.core.animation.animation_engine import evaluate_aurora_animation_pose

    directions = _coupled_defend_translation_directions(anim.name)
    state_lists = []
    segment_lists = []
    state_count_min = 1 << 30
    state_count_max = 0
    target_clearance = float(clearance)

    for time_value in solve_times:
        pose = evaluate_aurora_animation_pose(rigged, anim, float(time_value))
        world = _pose_world_by_name(pose)
        torso = world["torsoupr_g"]
        hand_body = {
            side: np.asarray(_point_in_frame(
                world[f"{side}hand_g"].position, torso), dtype=np.float64)
            for side in ("r", "l")
        }
        shoulder_body = {
            side: np.asarray(_point_in_frame(
                world[f"{side}bicep_g"].position, torso), dtype=np.float64)
            for side in ("r", "l")
        }
        reach = {}
        minimum_reach = {}
        for side in ("r", "l"):
            shoulder = world[f"{side}bicep_g"]
            elbow = world[f"{side}forearm_g"]
            hand = world[f"{side}hand_g"]
            upper = _math.dist(shoulder.position, elbow.position)
            lower = _math.dist(elbow.position, hand.position)
            reach[side] = float(upper + lower)
            minimum_reach[side] = float(abs(upper - lower))

        socket = world.get("rhand")
        if socket is None:
            raise AssertionError(f"{anim.name}: animated rhand socket missing")
        socket_q = tuple(float(component) for component in socket.rotation[:4])
        segment = []
        for local_point in RIGHT_SABER_CENTERLINE_LOCAL:
            point_world = tuple(
                float(a) + float(b) for a, b in zip(
                    socket.position,
                    _quat_rotate_vec_xyzw(socket_q, local_point),
                )
            )
            segment.append(np.asarray(
                _point_in_frame(point_world, torso), dtype=np.float64))
        segment_lists.append(tuple(segment))

        def valid_delta(delta):
            for side in ("r", "l"):
                candidate = hand_body[side] + delta
                if not _hand_body_outside_torso(candidate):
                    return False
                distance = float(np.linalg.norm(candidate - shoulder_body[side]))
                if (distance > reach[side] + 1.0e-6
                        or distance < minimum_reach[side] - 1.0e-6):
                    return False
            return True

        def surface_clearance(delta):
            return _segment_triangles_distance(
                segment[0] + delta,
                segment[1] + delta,
                head_triangles_body,
            )

        states_by_cell = {}

        def add_state(delta):
            delta = np.asarray(delta, dtype=np.float64)
            if not valid_delta(delta):
                return
            measured = float(surface_clearance(delta))
            if measured + 1.0e-9 < target_clearance:
                return
            cell = tuple(int(round(float(component) / 0.005)) for component in delta)
            prior = states_by_cell.get(cell)
            record = (delta, measured)
            if prior is None or float(np.linalg.norm(delta)) < float(
                    np.linalg.norm(prior[0])):
                states_by_cell[cell] = record

        zero = np.zeros(3, dtype=np.float64)
        base_clearance = float(surface_clearance(zero))
        if base_clearance >= target_clearance and valid_delta(zero):
            add_state(zero)

        for raw_direction in directions:
            direction = np.asarray(raw_direction, dtype=np.float64)
            maximum = 0.65
            for side in ("r", "l"):
                offset = hand_body[side] - shoulder_body[side]
                projection = float(offset @ direction)
                discriminant = (
                    projection * projection
                    + reach[side] * reach[side]
                    - float(offset @ offset)
                )
                if discriminant < -1.0e-8:
                    maximum = -1.0
                    break
                maximum = min(
                    maximum,
                    -projection + _math.sqrt(max(0.0, discriminant)),
                )
            if maximum <= 1.0e-6:
                continue

            first_safe = 0.0 if base_clearance >= target_clearance else None
            if first_safe is None:
                lower = 0.0
                step = 0.03
                samples = [
                    min(maximum, float(index) * step)
                    for index in range(1, int(_math.ceil(maximum / step)) + 1)
                ]
                for candidate_shift in samples:
                    candidate_delta = direction * candidate_shift
                    if (valid_delta(candidate_delta)
                            and surface_clearance(candidate_delta) >= target_clearance):
                        upper = candidate_shift
                        for _iteration in range(12):
                            midpoint = 0.5 * (lower + upper)
                            midpoint_delta = direction * midpoint
                            if (valid_delta(midpoint_delta)
                                    and surface_clearance(midpoint_delta)
                                    >= target_clearance):
                                upper = midpoint
                            else:
                                lower = midpoint
                        first_safe = float(upper)
                        break
                    lower = candidate_shift
            if first_safe is None:
                continue
            continuation_step = 0.03
            continuation_count = int(round(0.60 / continuation_step)) + 1
            for continuation in tuple(
                    continuation_step * index
                    for index in range(continuation_count)):
                shift = float(first_safe) + continuation
                if shift <= maximum + 1.0e-9:
                    add_state(direction * shift)

        if not states_by_cell:
            fraction = (
                float(time_value) / float(anim.length)
                if float(anim.length) > 1.0e-9 else 0.0)
            raise AssertionError(
                f"{anim.name}: no coupled two-hand saber clearance state at "
                f"{fraction:.1%} (base={base_clearance:.3f}m)")
        ordered = sorted(
            states_by_cell.values(),
            key=lambda record: (
                float(np.linalg.norm(record[0])),
                tuple(float(component) for component in record[0]),
            ),
        )
        states = np.asarray([record[0] for record in ordered], dtype=np.float64)
        state_lists.append(states)
        state_count_min = min(state_count_min, len(states))
        state_count_max = max(state_count_max, len(states))

    # Viterbi selection: small correction magnitude plus a time-aware velocity
    # term.  Transitions faster than the visible-motion limit are excluded,
    # rather than selected and rejected only after the whole path is built.
    backpointers = []
    previous_states = state_lists[0]
    first_dt = (
        max(1.0e-5, float(solve_times[1]) - float(solve_times[0]))
        if len(solve_times) > 1 else 1.0 / 120.0
    )
    previous_cost = (
        np.einsum("ij,ij->i", previous_states, previous_states) * first_dt
    )
    for step_index, states in enumerate(state_lists[1:], start=1):
        dt = max(
            1.0e-5,
            float(solve_times[step_index]) - float(solve_times[step_index - 1]),
        )
        difference = states[:, None, :] - previous_states[None, :, :]
        distance_sq = np.einsum("ijk,ijk->ij", difference, difference)
        distance = np.sqrt(distance_sq)
        transition = (
            float(COUPLED_DEFEND_VELOCITY_WEIGHT) * distance_sq / dt
        )
        transition = np.where(
            distance <= (
                float(COUPLED_DEFEND_MAX_CORRECTION_SPEED) * dt + 1.0e-6
            ),
            transition,
            np.inf,
        )
        total = transition + previous_cost[None, :]
        parents = np.argmin(total, axis=1)
        current_cost = (
            np.einsum("ij,ij->i", states, states) * dt
            + total[np.arange(len(states)), parents]
        )
        if not bool(np.isfinite(current_cost).any()):
            fraction = (
                float(solve_times[step_index]) / float(anim.length)
                if float(anim.length) > 1.0e-9 else 0.0
            )
            raise AssertionError(
                f"{anim.name}: no continuous coupled saber path at "
                f"{fraction:.1%} within "
                f"{COUPLED_DEFEND_MAX_CORRECTION_SPEED:.1f}m/s")
        backpointers.append(parents)
        previous_states = states
        previous_cost = current_cost

    selected_indices = [int(np.argmin(previous_cost))]
    for parents in reversed(backpointers):
        selected_indices.append(int(parents[selected_indices[-1]]))
    selected_indices.reverse()
    selected = [
        np.asarray(states[index], dtype=np.float64)
        for states, index in zip(state_lists, selected_indices)
    ]
    jumps = [
        float(np.linalg.norm(current - prior))
        for prior, current in zip(selected, selected[1:])
    ]
    max_jump = max(jumps, default=0.0)
    speeds = [
        jump / max(1.0e-5, float(current_time) - float(prior_time))
        for jump, prior_time, current_time in zip(
            jumps, solve_times, solve_times[1:])
    ]
    max_speed = max(speeds, default=0.0)
    if max_speed > float(COUPLED_DEFEND_MAX_CORRECTION_SPEED):
        raise AssertionError(
            f"{anim.name}: coupled saber correction moves at "
            f"{max_speed:.3f}m/s")
    planned_clearances = [
        _segment_triangles_distance(
            segment[0] + delta,
            segment[1] + delta,
            head_triangles_body,
        )
        for segment, delta in zip(segment_lists, selected)
    ]
    return selected, {
        "max_hand_shift": max(
            (float(np.linalg.norm(delta)) for delta in selected), default=0.0),
        "max_jump": max_jump,
        "max_speed": max_speed,
        "min_planned_clearance": min(planned_clearances),
        "state_count_min": int(state_count_min),
        "state_count_max": int(state_count_max),
    }


def _continuous_elbow_pole_body(
        shoulder_body, elbow_body, goal_body, previous_bend_body=None):
    """Choose a torso-space elbow pole without crossing the bend singularity.

    A two-bone chain has two mirrored elbow solutions.  When the arm passes
    close to straight, the projected authored pole becomes tiny and numerical
    noise can select the opposite solution on the next key.  Project the prior
    bend direction into the new shoulder-goal plane, align the authored pole
    to that hemisphere, and carry the prior direction through the singular
    region.  The result remains a position pole, so the shared math solver does
    not need any animation-specific policy.
    """
    import numpy as np

    shoulder = np.asarray(shoulder_body, dtype=np.float64)
    elbow = np.asarray(elbow_body, dtype=np.float64)
    goal = np.asarray(goal_body, dtype=np.float64)
    aim = goal - shoulder
    aim_length = float(np.linalg.norm(aim))
    aim_direction = (
        aim / aim_length
        if aim_length > 1.0e-9 else np.asarray((0.0, 1.0, 0.0))
    )

    def projected_unit(raw_direction):
        direction = np.asarray(raw_direction, dtype=np.float64)
        projected = direction - aim_direction * float(direction @ aim_direction)
        magnitude = float(np.linalg.norm(projected))
        return (
            projected / magnitude if magnitude > 1.0e-9 else None,
            magnitude,
        )

    authored_direction, authored_magnitude = projected_unit(elbow - shoulder)
    prior_direction = None
    if previous_bend_body is not None:
        prior_direction, _prior_magnitude = projected_unit(previous_bend_body)

    if authored_direction is None:
        bend_direction = prior_direction
    elif prior_direction is None:
        bend_direction = authored_direction
    else:
        if float(authored_direction @ prior_direction) < 0.0:
            authored_direction = -authored_direction
        # Inside this narrow region the authored side is ill-conditioned;
        # parallel transport of the preceding bend plane is the stable limit.
        bend_direction = (
            prior_direction
            if authored_magnitude < 0.02 else authored_direction
        )

    if bend_direction is None:
        cardinals = (
            np.asarray((1.0, 0.0, 0.0)),
            np.asarray((0.0, 1.0, 0.0)),
            np.asarray((0.0, 0.0, 1.0)),
        )
        fallback = min(
            cardinals,
            key=lambda axis: abs(float(axis @ aim_direction)),
        )
        bend_direction, _magnitude = projected_unit(fallback)
    if bend_direction is None:
        raise AssertionError("could not resolve a continuous elbow bend pole")

    pole_radius = max(0.10, float(np.linalg.norm(elbow - shoulder)))
    return shoulder + bend_direction * pole_radius, bend_direction


def _retarget_set4_elbow_pole_body(
        source_world, target_world, side, goal_body,
        previous_bend_body=None):
    """Map the donor bend plane, not its absolute humanoid elbow point.

    Absolute elbow positions collapse against the Ithorian's differently
    placed shoulders.  A normalized donor bend direction is morphology-free:
    project it into the target shoulder-to-goal plane, scale it by the target
    upper-arm length, and hemisphere-align it to the preceding 60 Hz key.
    Near a straight donor arm, parallel-transport the prior direction instead
    of selecting a numerically arbitrary mirrored elbow branch.
    """
    import math as _math
    import numpy as np

    source_torso = source_world["torsoupr_g"]
    source_shoulder = np.asarray(_point_in_frame(
        source_world[f"{side}bicep_g"].position, source_torso),
        dtype=np.float64,
    )
    source_elbow = np.asarray(_point_in_frame(
        source_world[f"{side}forearm_g"].position, source_torso),
        dtype=np.float64,
    )
    source_hand = np.asarray(_point_in_frame(
        source_world[f"{side}hand_g"].position, source_torso),
        dtype=np.float64,
    )
    source_aim = source_hand - source_shoulder
    source_aim_length = float(np.linalg.norm(source_aim))
    source_bend = source_elbow - source_shoulder
    source_upper_length = max(
        1.0e-9,
        _math.dist(
            source_world[f"{side}bicep_g"].position,
            source_world[f"{side}forearm_g"].position,
        ),
    )
    if source_aim_length > 1.0e-9:
        source_aim_direction = source_aim / source_aim_length
        source_bend = source_bend - source_aim_direction * float(
            source_bend @ source_aim_direction)
    source_bend_height = float(np.linalg.norm(source_bend))
    source_bend_ratio = source_bend_height / source_upper_length

    target_torso = target_world["torsoupr_g"]
    target_shoulder = np.asarray(_point_in_frame(
        target_world[f"{side}bicep_g"].position, target_torso),
        dtype=np.float64,
    )
    target_upper_length = _math.dist(
        target_world[f"{side}bicep_g"].position,
        target_world[f"{side}forearm_g"].position,
    )
    if (source_bend_height > 1.0e-9
            and (source_bend_ratio >= 0.10
                 or previous_bend_body is None)):
        authored_elbow = (
            target_shoulder
            + source_bend / source_bend_height * float(target_upper_length)
        )
    else:
        # A zero authored direction tells _continuous_elbow_pole_body to carry
        # the previous bend through this near-straight singularity.
        authored_elbow = target_shoulder
    pole_body, bend_direction = _continuous_elbow_pole_body(
        target_shoulder,
        authored_elbow,
        goal_body,
        previous_bend_body,
    )
    return pole_body, bend_direction, source_bend_ratio


def _apply_coupled_defend_deltas(
        anim, rigged, solve_times, tracks, rig_by_name, selected_deltas):
    """Bake a planned shared hand translation into both two-bone arm chains."""
    import math as _math
    import numpy as np
    from src.core.animation.animation_engine import evaluate_aurora_animation_pose
    from src.math.limb_ik import solve_two_bone_positions

    max_landing_error = 0.0
    max_grip_vector_error = 0.0
    max_elbow_pole_bias = 0.0
    previous_bend_body = {"r": None, "l": None}
    for key_index, (time_value, delta_body) in enumerate(zip(
            solve_times, selected_deltas)):
        base_pose = evaluate_aurora_animation_pose(rigged, anim, float(time_value))
        base_world = _pose_world_by_name(base_pose)
        base_torso = base_world["torsoupr_g"]
        base_hand_body = {
            side: np.asarray(_point_in_frame(
                base_world[f"{side}hand_g"].position, base_torso),
                dtype=np.float64,
            )
            for side in ("r", "l")
        }
        base_grip_vector = base_hand_body["l"] - base_hand_body["r"]
        original_hand_q = {
            side: tuple(float(component) for component in
                        base_world[f"{side}hand_g"].rotation[:4])
            for side in ("r", "l")
        }

        for side in ("r", "l"):
            target_pose = evaluate_aurora_animation_pose(
                rigged, anim, float(time_value))
            target_world = _pose_world_by_name(target_pose)
            torso = target_world["torsoupr_g"]
            shoulder = target_world[f"{side}bicep_g"]
            elbow = target_world[f"{side}forearm_g"]
            hand = target_world[f"{side}hand_g"]
            goal_body = base_hand_body[side] + np.asarray(
                delta_body, dtype=np.float64)
            goal_world = _point_from_frame(tuple(goal_body), torso)
            shoulder_body = np.asarray(_point_in_frame(
                shoulder.position, torso), dtype=np.float64)
            elbow_body = np.asarray(_point_in_frame(
                elbow.position, torso), dtype=np.float64)
            pole_body, bend_body = _continuous_elbow_pole_body(
                shoulder_body,
                elbow_body,
                goal_body,
                previous_bend_body[side],
            )
            previous_bend_body[side] = bend_body
            pole_world = _point_from_frame(tuple(pole_body), torso)
            # Preserve the base IK bend plane while keeping it on one
            # continuous hemisphere.  Near a straight-arm singularity the
            # projected base pole can change sign between adjacent 240 Hz
            # keys; following that sign flip makes quaternion interpolation
            # throw the long Ithorian elbow across the body between keys.
            solution = solve_two_bone_positions(
                shoulder.position,
                elbow.position,
                hand.position,
                goal_world,
                pole_world,
            )
            if float(solution.residual) > 0.003:
                raise AssertionError(
                    f"{anim.name} {side} coupled goal projected by "
                    f"{float(solution.residual):.4f}m at {time_value:.5f}")

            shoulder_delta = _quat_between_vecs(
                tuple(float(a) - float(b) for a, b in zip(
                    elbow.position, shoulder.position)),
                tuple(float(a) - float(b) for a, b in zip(
                    solution.elbow_position, shoulder.position)),
            )
            new_shoulder_world = _quat_norm_xyzw(_quat_mul_xyzw(
                shoulder_delta,
                tuple(float(component) for component in shoulder.rotation[:4]),
            ))
            shoulder_parent = rig_by_name[f"{side}bicep_g"].parent
            parent_world = target_world[
                str(shoulder_parent.name or "").strip().lower()]
            tracks[f"{side}bicep_g"]["values"][key_index] = list(
                _quat_norm_xyzw(_quat_mul_xyzw(
                    _quat_inv_xyzw(tuple(float(component) for component in
                                          parent_world.rotation[:4])),
                    new_shoulder_world,
                )))

            target_pose = evaluate_aurora_animation_pose(
                rigged, anim, float(time_value))
            target_world = _pose_world_by_name(target_pose)
            elbow = target_world[f"{side}forearm_g"]
            hand = target_world[f"{side}hand_g"]
            elbow_delta = _quat_between_vecs(
                tuple(float(a) - float(b) for a, b in zip(
                    hand.position, elbow.position)),
                tuple(float(a) - float(b) for a, b in zip(
                    solution.target_position, elbow.position)),
            )
            new_elbow_world = _quat_norm_xyzw(_quat_mul_xyzw(
                elbow_delta,
                tuple(float(component) for component in elbow.rotation[:4]),
            ))
            elbow_parent = rig_by_name[f"{side}forearm_g"].parent
            parent_world = target_world[
                str(elbow_parent.name or "").strip().lower()]
            tracks[f"{side}forearm_g"]["values"][key_index] = list(
                _quat_norm_xyzw(_quat_mul_xyzw(
                    _quat_inv_xyzw(tuple(float(component) for component in
                                          parent_world.rotation[:4])),
                    new_elbow_world,
                )))

            target_pose = evaluate_aurora_animation_pose(
                rigged, anim, float(time_value))
            target_world = _pose_world_by_name(target_pose)
            hand_parent = rig_by_name[f"{side}hand_g"].parent
            parent_world = target_world[
                str(hand_parent.name or "").strip().lower()]
            tracks[f"{side}hand_g"]["values"][key_index] = list(
                _quat_norm_xyzw(_quat_mul_xyzw(
                    _quat_inv_xyzw(tuple(float(component) for component in
                                          parent_world.rotation[:4])),
                    original_hand_q[side],
                )))

            solved_pose = evaluate_aurora_animation_pose(
                rigged, anim, float(time_value))
            solved_hand = _pose_world_by_name(
                solved_pose)[f"{side}hand_g"]
            landing_error = _math.dist(
                solved_hand.position, solution.target_position)
            max_landing_error = max(max_landing_error, landing_error)
            if landing_error > 0.001:
                raise AssertionError(
                    f"{anim.name} {side} coupled IK miss at {time_value:.5f}: "
                    f"{landing_error:.6f}m")

        solved_pose = evaluate_aurora_animation_pose(
            rigged, anim, float(time_value))
        solved_world = _pose_world_by_name(solved_pose)
        solved_torso = solved_world["torsoupr_g"]
        solved_grip_vector = (
            np.asarray(_point_in_frame(
                solved_world["lhand_g"].position, solved_torso), dtype=np.float64)
            - np.asarray(_point_in_frame(
                solved_world["rhand_g"].position, solved_torso), dtype=np.float64)
        )
        max_grip_vector_error = max(
            max_grip_vector_error,
            float(np.linalg.norm(solved_grip_vector - base_grip_vector)),
        )

    if max_grip_vector_error > 0.01:
        raise AssertionError(
            f"{anim.name}: coupled grip vector drifted "
            f"{max_grip_vector_error:.4f}m")
    return {
        "max_landing_error": max_landing_error,
        "max_grip_vector_error": max_grip_vector_error,
        "max_elbow_pole_bias": max_elbow_pole_bias,
    }


def _resample_delta_path(
        source_times, source_deltas, target_times, *, spherical=False):
    """Resample a continuous torso-space correction trajectory.

    Linear interpolation is appropriate within one clearance branch.  c2d2
    changes elevation branches around the skull, where the Cartesian chord
    crosses the obstacle; spherical direction interpolation follows the safe
    arc instead while blending correction magnitude normally.
    """
    import bisect
    import math as _math
    import numpy as np

    source_times = tuple(float(value) for value in source_times)
    source_deltas = tuple(
        np.asarray(value, dtype=np.float64) for value in source_deltas)
    if not source_times or len(source_times) != len(source_deltas):
        raise AssertionError("coupled delta path is empty or misaligned")
    result = []
    for raw_time in target_times:
        time_value = float(raw_time)
        upper = bisect.bisect_left(source_times, time_value)
        if upper <= 0:
            result.append(np.asarray(source_deltas[0], dtype=np.float64))
            continue
        if upper >= len(source_times):
            result.append(np.asarray(source_deltas[-1], dtype=np.float64))
            continue
        lower = upper - 1
        span = source_times[upper] - source_times[lower]
        weight = (
            (time_value - source_times[lower]) / span
            if span > 1.0e-9 else 0.0
        )
        lower_delta = source_deltas[lower]
        upper_delta = source_deltas[upper]
        if spherical:
            lower_radius = float(np.linalg.norm(lower_delta))
            upper_radius = float(np.linalg.norm(upper_delta))
            if lower_radius > 1.0e-9 and upper_radius > 1.0e-9:
                lower_direction = lower_delta / lower_radius
                upper_direction = upper_delta / upper_radius
                dot = max(-1.0, min(1.0, float(
                    lower_direction @ upper_direction)))
                angle = _math.acos(dot)
                sine = _math.sin(angle)
                if abs(sine) > 1.0e-6:
                    direction = (
                        lower_direction
                        * (_math.sin((1.0 - weight) * angle) / sine)
                        + upper_direction
                        * (_math.sin(weight * angle) / sine)
                    )
                    radius = (
                        lower_radius * (1.0 - weight)
                        + upper_radius * weight
                    )
                    result.append(direction * radius)
                    continue
        result.append(
            lower_delta * (1.0 - weight) + upper_delta * weight)
    return result


def audit_coupled_defend_delta_path(
        anim, rigged, sample_times, sample_deltas, head_triangles_body, *,
        include_midpoints=True, transition_substeps=None):
    """Audit a proposed shared-hand path before it is converted to IK keys.

    The sparse planner previously proved only its own endpoints.  This gate
    measures the actual bake path (and its linear target-space midpoints) in
    animated torso space, so a branch change cannot tunnel the saber through
    the head between otherwise valid states.
    """
    import math as _math
    import numpy as np

    times = tuple(float(value) for value in sample_times)
    deltas = tuple(np.asarray(value, dtype=np.float64) for value in sample_deltas)
    if not times or len(times) != len(deltas):
        raise AssertionError("coupled path audit received empty/misaligned data")
    if any(not _math.isfinite(value) for value in times):
        raise AssertionError("coupled path audit received a non-finite time")
    if any(not bool(np.isfinite(delta).all()) for delta in deltas):
        raise AssertionError("coupled path audit received a non-finite delta")
    if any(current <= prior for prior, current in zip(times, times[1:])):
        raise AssertionError("coupled path audit times are not strictly increasing")

    max_speed = 0.0
    max_speed_time = times[0]
    for prior_time, time_value, prior_delta, delta in zip(
            times, times[1:], deltas, deltas[1:]):
        dt = float(time_value) - float(prior_time)
        speed = float(np.linalg.norm(delta - prior_delta)) / dt
        if speed > max_speed:
            max_speed = speed
            max_speed_time = float(time_value)

    audit_samples = list(zip(times, deltas))
    substeps = int(
        transition_substeps
        if transition_substeps is not None else (2 if include_midpoints else 1)
    )
    if substeps < 1:
        raise AssertionError("coupled path audit substeps must be positive")
    if substeps > 1:
        audit_samples.extend(
            (
                float(prior_time) + (
                    float(time_value) - float(prior_time)) * fraction,
                prior_delta + (delta - prior_delta) * fraction,
            )
            for prior_time, time_value, prior_delta, delta in zip(
                times, times[1:], deltas, deltas[1:])
            for fraction in (
                float(index) / float(substeps)
                for index in range(1, substeps)
            )
        )
        audit_samples.sort(key=lambda record: float(record[0]))

    minimum_clearance = float("inf")
    minimum_clearance_time = times[0]
    torso_violations = 0
    reach_violations = 0
    max_reach_excess = 0.0
    max_reach_deficit = 0.0
    for time_value, delta in audit_samples:
        context = _coupled_defend_frame_context(anim, rigged, time_value)
        status = _coupled_defend_delta_status(
            context, delta, head_triangles_body)
        if float(status["clearance"]) < minimum_clearance:
            minimum_clearance = float(status["clearance"])
            minimum_clearance_time = float(time_value)
        torso_violations += int(status["torso_violations"])
        reach_violations += int(status["reach_violations"])
        max_reach_excess = max(
            max_reach_excess, float(status["max_reach_excess"]))
        max_reach_deficit = max(
            max_reach_deficit, float(status["max_reach_deficit"]))

    length = max(0.0, float(getattr(anim, "length", 0.0) or 0.0))
    return {
        "samples": len(audit_samples),
        "max_speed": float(max_speed),
        "max_speed_time": float(max_speed_time),
        "min_clearance": float(minimum_clearance),
        "min_clearance_time": float(minimum_clearance_time),
        "min_clearance_fraction": (
            float(minimum_clearance_time) / length
            if length > 1.0e-9 else 0.0),
        "torso_violations": int(torso_violations),
        "reach_violations": int(reach_violations),
        "max_reach_excess": float(max_reach_excess),
        "max_reach_deficit": float(max_reach_deficit),
    }


def _refine_coupled_defend_delta_path(
        anim, rigged, sample_times, guide_deltas, head_triangles_body, *,
        clearance, max_speed=COUPLED_DEFEND_MAX_CORRECTION_SPEED,
        beam_width=COUPLED_CONTINUATION_BEAM_WIDTH,
        window_padding=COUPLED_CONTINUATION_WINDOW_PADDING,
        window_padding_before=None,
        window_padding_after=None,
        transition_substeps=COUPLED_CONTINUATION_TRANSITION_SUBSTEPS):
    """Repair unsafe guide intervals with a bounded space-time beam search.

    States are absolute shared-hand translations in animated torso space.  A
    transition is admitted only when its endpoint and every configured
    target-space substep satisfy both arm reach shells, the robe capsule, and
    the exact posed-head triangle distance.  Padding lets the path begin its
    detour before a coarse branch switch consumes the entire per-frame motion
    budget.
    """
    import itertools
    import math as _math
    import numpy as np

    times = tuple(float(value) for value in sample_times)
    guide = tuple(np.asarray(value, dtype=np.float64) for value in guide_deltas)
    if not times or len(times) != len(guide):
        raise AssertionError("coupled continuation guide is empty or misaligned")
    if any(current <= prior for prior, current in zip(times, times[1:])):
        raise AssertionError("coupled continuation times are not increasing")

    context_cache = {}
    status_cache = {}
    target_clearance = float(clearance)
    speed_limit = float(max_speed)
    cell_size = float(COUPLED_CONTINUATION_CELL_SIZE)
    transition_substeps = int(transition_substeps)
    if transition_substeps < 2:
        raise AssertionError(
            "coupled continuation transition_substeps must be at least two")
    transition_fractions = tuple(
        float(index) / float(transition_substeps)
        for index in range(1, transition_substeps)
    )

    def context_at(time_value):
        key = round(float(time_value), 9)
        context = context_cache.get(key)
        if context is None:
            context = _coupled_defend_frame_context(anim, rigged, time_value)
            context_cache[key] = context
        return context

    def delta_cell(delta):
        return tuple(
            int(round(float(component) / cell_size)) for component in delta)

    def status_at(time_value, delta):
        delta = np.asarray(delta, dtype=np.float64)
        key = (float(time_value).hex(), delta.tobytes())
        status = status_cache.get(key)
        if status is None:
            status = _coupled_defend_delta_status(
                context_at(time_value), delta, head_triangles_body)
            status_cache[key] = status
        return status

    def status_is_safe(status):
        return (
            int(status["torso_violations"]) == 0
            and int(status["reach_violations"]) == 0
            and float(status["clearance"]) + 1.0e-9 >= target_clearance
        )

    bad_indices = set()
    for index, (time_value, delta) in enumerate(zip(times, guide)):
        if not status_is_safe(status_at(time_value, delta)):
            bad_indices.add(index)
    for index, (prior_time, time_value, prior_delta, delta) in enumerate(zip(
            times, times[1:], guide, guide[1:]), start=1):
        dt = float(time_value) - float(prior_time)
        speed = float(np.linalg.norm(delta - prior_delta)) / dt
        transition_is_safe = True
        for fraction in transition_fractions:
            probe_time = float(prior_time) + dt * fraction
            probe_delta = prior_delta + (delta - prior_delta) * fraction
            if not status_is_safe(status_at(probe_time, probe_delta)):
                transition_is_safe = False
                break
        if speed > speed_limit + 1.0e-6 or not transition_is_safe:
            bad_indices.update((index - 1, index))

    if not bad_indices:
        audit = audit_coupled_defend_delta_path(
            anim,
            rigged,
            times,
            guide,
            head_triangles_body,
            include_midpoints=True,
            transition_substeps=transition_substeps,
        )
        return list(guide), {
            "refined": False,
            "bad_samples": 0,
            "window_start": 0,
            "window_end": 0,
            "expanded_candidates": 0,
            "accepted_candidates": 0,
            "audit": audit,
        }

    before_padding = int(
        window_padding
        if window_padding_before is None else window_padding_before)
    after_padding = int(
        window_padding
        if window_padding_after is None else window_padding_after)
    start_index = max(0, min(bad_indices) - before_padding)
    end_index = min(len(times) - 1, max(bad_indices) + after_padding)
    while start_index > 0 and not status_is_safe(status_at(
            times[start_index], guide[start_index])):
        start_index -= 1
    while end_index + 1 < len(times) and not status_is_safe(status_at(
            times[end_index], guide[end_index])):
        end_index += 1
    if not status_is_safe(status_at(times[start_index], guide[start_index])):
        raise AssertionError(
            f"{anim.name}: coupled continuation has no safe start anchor")
    if not status_is_safe(status_at(times[end_index], guide[end_index])):
        raise AssertionError(
            f"{anim.name}: coupled continuation has no safe end anchor")

    directions = []
    for raw in itertools.product((-1.0, 0.0, 1.0), repeat=3):
        length = _math.sqrt(sum(component * component for component in raw))
        if length <= 1.0e-9:
            continue
        directions.append(np.asarray(
            tuple(component / length for component in raw),
            dtype=np.float64,
        ))

    start_record = {
        "delta": np.asarray(guide[start_index], dtype=np.float64),
        "cost": 0.0,
        "parent": -1,
        "clearance": float(status_at(
            times[start_index], guide[start_index])["clearance"]),
    }
    layers = [[start_record]]
    expanded_candidates = 0
    accepted_candidates = 1

    def append_unique(selected, record, seen):
        key = delta_cell(record["delta"])
        if key in seen or len(selected) >= int(beam_width):
            return
        seen.add(key)
        selected.append(record)

    for step_index in range(start_index + 1, end_index + 1):
        previous = layers[-1]
        time_value = times[step_index]
        prior_time = times[step_index - 1]
        dt = float(time_value) - float(prior_time)
        step_limit = speed_limit * dt
        step_radius = max(0.0, step_limit - 2.0e-7)
        end_time = times[end_index]
        end_delta = guide[end_index]
        remaining_time = max(0.0, float(end_time) - float(time_value))
        force_anchor = step_index == end_index
        options_by_cell = {}

        for parent_index, parent in enumerate(previous):
            prior_delta = np.asarray(parent["delta"], dtype=np.float64)
            candidates = []
            if force_anchor:
                if float(np.linalg.norm(end_delta - prior_delta)) <= step_limit + 1.0e-9:
                    candidates.append(np.asarray(end_delta, dtype=np.float64))
            else:
                candidates.append(prior_delta)
                toward_guide = guide[step_index] - prior_delta
                guide_distance = float(np.linalg.norm(toward_guide))
                if guide_distance <= step_limit + 1.0e-9:
                    candidates.append(np.asarray(
                        guide[step_index], dtype=np.float64))
                elif guide_distance > 1.0e-9:
                    candidates.append(
                        prior_delta + toward_guide * (step_radius / guide_distance))
                toward_end = end_delta - prior_delta
                end_distance = float(np.linalg.norm(toward_end))
                if end_distance > 1.0e-9:
                    candidates.append(
                        prior_delta + toward_end * (
                            min(step_radius, end_distance) / end_distance))
                candidates.extend(
                    prior_delta + direction * step_radius
                    for direction in directions
                )
                candidates.extend(
                    prior_delta + direction * (0.5 * step_radius)
                    for direction in directions
                    if sum(abs(float(component)) > 1.0e-9
                           for component in direction) == 1
                )

            for candidate in candidates:
                expanded_candidates += 1
                candidate = np.asarray(candidate, dtype=np.float64)
                movement = float(np.linalg.norm(candidate - prior_delta))
                if movement > step_limit + 1.0e-9:
                    continue
                if (float(np.linalg.norm(end_delta - candidate))
                        > speed_limit * remaining_time + cell_size):
                    continue
                tracking = float(np.linalg.norm(
                    candidate - guide[step_index])) ** 2
                magnitude = float(np.linalg.norm(candidate)) ** 2
                transition = movement * movement / max(dt, 1.0e-9)
                cost = (
                    float(parent["cost"])
                    + dt * (tracking + 0.03 * magnitude)
                    + 0.001 * transition
                )
                cell = delta_cell(candidate)
                option = (cost, parent_index, candidate)
                cell_options = options_by_cell.setdefault(cell, {})
                prior_option = cell_options.get(parent_index)
                if (prior_option is None
                        or float(option[0]) < float(prior_option[0])):
                    cell_options[parent_index] = option

        records = []
        for cell in sorted(options_by_cell):
            ordered_options = sorted(
                options_by_cell[cell].values(),
                key=lambda record: (
                    float(record[0]), int(record[1]),
                    tuple(float(component) for component in record[2]),
                ),
            )
            for cost, parent_index, candidate in ordered_options:
                current_status = status_at(time_value, candidate)
                if not status_is_safe(current_status):
                    continue
                prior_delta = np.asarray(
                    previous[parent_index]["delta"], dtype=np.float64)
                transition_clearance = float(current_status["clearance"])
                transition_is_safe = True
                for fraction in transition_fractions:
                    probe_time = float(prior_time) + dt * fraction
                    probe_delta = (
                        prior_delta + (candidate - prior_delta) * fraction)
                    probe_status = status_at(probe_time, probe_delta)
                    if not status_is_safe(probe_status):
                        transition_is_safe = False
                        break
                    transition_clearance = min(
                        transition_clearance,
                        float(probe_status["clearance"]),
                    )
                if not transition_is_safe:
                    continue
                records.append({
                    "delta": candidate,
                    "cost": float(cost),
                    "parent": int(parent_index),
                    "clearance": transition_clearance,
                })
                break

        if not records:
            fraction = (
                float(time_value) / float(anim.length)
                if float(anim.length) > 1.0e-9 else 0.0)
            raise AssertionError(
                f"{anim.name}: continuation beam exhausted at {fraction:.1%} "
                f"({step_index - start_index}/{end_index - start_index})")

        records.sort(key=lambda record: (
            float(record["cost"]),
            tuple(float(component) for component in record["delta"]),
        ))
        selected = []
        selected_cells = set()
        low_cost_count = max(1, int(beam_width) // 2)
        for record in records[:low_cost_count]:
            append_unique(selected, record, selected_cells)

        for record in sorted(records, key=lambda candidate: (
                -float(candidate["clearance"]),
                float(candidate["cost"]),
                tuple(float(component) for component in candidate["delta"]),
        )):
            if len(selected) >= max(low_cost_count, 3 * int(beam_width) // 4):
                break
            append_unique(selected, record, selected_cells)

        bucket_best = {}
        for record in records:
            relative = np.asarray(record["delta"]) - guide[step_index]
            bucket = tuple(
                int(_math.floor(float(component) / 0.04))
                for component in relative
            )
            prior = bucket_best.get(bucket)
            if prior is None or float(record["cost"]) < float(prior["cost"]):
                bucket_best[bucket] = record
        for bucket in sorted(bucket_best):
            append_unique(selected, bucket_best[bucket], selected_cells)
        for record in records:
            append_unique(selected, record, selected_cells)
        layers.append(selected)
        accepted_candidates += len(selected)

    final_index = min(
        range(len(layers[-1])),
        key=lambda index: float(layers[-1][index]["cost"]),
    )
    window_path = []
    parent_index = int(final_index)
    for layer in reversed(layers):
        record = layer[parent_index]
        window_path.append(np.asarray(record["delta"], dtype=np.float64))
        parent_index = int(record["parent"])
    window_path.reverse()
    if len(window_path) != end_index - start_index + 1:
        raise AssertionError(f"{anim.name}: continuation backtrack length mismatch")

    refined = list(guide)
    refined[start_index:end_index + 1] = window_path
    audit = audit_coupled_defend_delta_path(
        anim,
        rigged,
        times,
        refined,
        head_triangles_body,
        include_midpoints=True,
        transition_substeps=transition_substeps,
    )
    if audit["max_speed"] > speed_limit + 1.0e-6:
        raise AssertionError(
            f"{anim.name}: refined correction moves at "
            f"{audit['max_speed']:.3f}m/s")
    if audit["min_clearance"] + 1.0e-9 < target_clearance:
        raise AssertionError(
            f"{anim.name}: refined blade/head clearance is "
            f"{audit['min_clearance']:.4f}m at "
            f"{audit['min_clearance_fraction']:.1%}")
    if audit["torso_violations"] or audit["reach_violations"]:
        raise AssertionError(
            f"{anim.name}: refined path has "
            f"{audit['torso_violations']} torso and "
            f"{audit['reach_violations']} reach violations")
    return refined, {
        "refined": True,
        "bad_samples": len(bad_indices),
        "window_start": int(start_index),
        "window_end": int(end_index),
        "expanded_candidates": int(expanded_candidates),
        "accepted_candidates": int(accepted_candidates),
        "audit": audit,
    }


def _sample_torso_grip_vectors(anim, rigged, sample_times):
    """Return the two-hand grip vector in animated torso space per sample."""
    import numpy as np
    from src.core.animation.animation_engine import evaluate_aurora_animation_pose

    result = []
    for time_value in sample_times:
        world = _pose_world_by_name(evaluate_aurora_animation_pose(
            rigged, anim, float(time_value)))
        torso = world["torsoupr_g"]
        left = np.asarray(_point_in_frame(
            world["lhand_g"].position, torso), dtype=np.float64)
        right = np.asarray(_point_in_frame(
            world["rhand_g"].position, torso), dtype=np.float64)
        result.append((
            float(time_value),
            tuple(float(component) for component in left - right),
        ))
    return tuple(result)


def audit_grip_against_baseline(anim, rigged, baseline):
    """Measure final two-hand interpolation against the pre-overlay curve."""
    import math as _math

    baseline = tuple(baseline or ())
    actual = _sample_torso_grip_vectors(
        anim, rigged, [time_value for time_value, _vector in baseline])
    max_error = 0.0
    max_time = 0.0
    for (time_value, expected), (_actual_time, measured) in zip(
            baseline, actual):
        error = _math.dist(expected, measured)
        if error > max_error:
            max_error = float(error)
            max_time = float(time_value)
    length = max(0.0, float(getattr(anim, "length", 0.0) or 0.0))
    return {
        "samples": len(baseline),
        "max_grip_vector_error": max_error,
        "max_time": max_time,
        "max_fraction": max_time / length if length > 1.0e-9 else 0.0,
    }


def _uses_coupled_saber_surface_goal(clip_name, source_clip_name):
    """Keep the costly two-hand planner limited to genuine Set 2 payloads."""
    clip_name = str(clip_name or "").strip().lower()
    source_clip_name = str(source_clip_name or "").strip().lower()
    return (
        clip_name in SABER_SURFACE_GOAL_CLIPS
        and source_clip_name == clip_name
        and source_clip_name not in SET4_ASSIGNED_SOURCE_CLIPS
    )


def _uses_set4_saber_surface_goal(clip_name, source_clip_name):
    """Return whether this slot needs the one-hand saber-surface planner."""
    clip_name = str(clip_name or "").strip().lower()
    source_clip_name = str(source_clip_name or "").strip().lower()
    legacy_set4 = (
        clip_name in SET4_ASSIGNED_CLIPS
        and source_clip_name in SET4_ASSIGNED_SOURCE_CLIPS
    )
    malak_collision = (
        clip_name in MALAK_SABER_SURFACE_GOAL_CLIPS
        and source_clip_name in set(MALAK_COMBAT_SLOT_SOURCES.values())
    )
    return legacy_set4 or malak_collision


def _right_saber_segment_in_torso(target_world):
    """Return the attached blade centreline in animated torso space."""
    import numpy as np

    socket = target_world.get("rhand")
    if socket is None:
        raise AssertionError("animated rhand socket missing")
    torso = target_world["torsoupr_g"]
    socket_q = tuple(float(component) for component in socket.rotation[:4])
    points = []
    for local_point in RIGHT_SABER_CENTERLINE_LOCAL:
        point_world = tuple(
            float(a) + float(b) for a, b in zip(
                socket.position,
                _quat_rotate_vec_xyzw(socket_q, local_point),
            )
        )
        points.append(np.asarray(
            _point_in_frame(point_world, torso), dtype=np.float64))
    return tuple(points)


_SET4_SABER_PLAN_CACHE = {}
_SET4_SABER_DISK_CACHE_SCHEMA = 1
# Explicit solver-policy revision for the durable canonical-plan cache.  Cache
# hits are geometrically revalidated against the current model, IK runtime,
# torso gate, speed limit, and exact head surface before use.  Keep this value
# stable for audit/reporting-only edits; bump it whenever the Set 4 planning or
# collision policy changes.
_SET4_SABER_SOLVER_POLICY_REVISION = (
    "de77fbaa057d4d30503ad541d0c1edfe"
    "129465c681ac16f81b9f95490d0f162e"
)
_SET4_SABER_DISK_CACHE_DIR = (
    ROOT / "artifacts" / "sith_ithorian_set4_plan_cache")
_SET4_SABER_DISK_CACHE_CONTEXT = None


def _set4_saber_solver_policy_sha256():
    """Return the explicit revision for Set 4 trajectory selection policy."""
    return str(_SET4_SABER_SOLVER_POLICY_REVISION)


def _reset_set4_saber_plan_cache():
    """Separate build variants and disable disk reuse until export is known."""
    global _SET4_SABER_DISK_CACHE_CONTEXT

    _SET4_SABER_PLAN_CACHE.clear()
    _SET4_SABER_DISK_CACHE_CONTEXT = None


def _set_set4_saber_disk_cache_context(initial_mdl, initial_mdx):
    """Enable strict cross-process reuse for one uncorrected exported model."""
    import hashlib

    global _SET4_SABER_DISK_CACHE_CONTEXT
    _SET4_SABER_PLAN_CACHE.clear()
    _SET4_SABER_DISK_CACHE_CONTEXT = {
        "initial_mdl_sha256": hashlib.sha256(initial_mdl).hexdigest(),
        "initial_mdx_sha256": hashlib.sha256(initial_mdx).hexdigest(),
        "solver_policy_sha256": _set4_saber_solver_policy_sha256(),
    }
    return dict(_SET4_SABER_DISK_CACHE_CONTEXT)


def _set4_saber_disk_cache_metadata(source_clip_name, solve_times):
    """Build the exact identity required for a reusable canonical plan."""
    if _SET4_SABER_DISK_CACHE_CONTEXT is None:
        return None
    metadata = {
        "schema": int(_SET4_SABER_DISK_CACHE_SCHEMA),
        **dict(_SET4_SABER_DISK_CACHE_CONTEXT),
        "source_clip": str(source_clip_name or "").strip().lower(),
        "solve_times": [round(float(value), 7) for value in solve_times],
    }
    required_clearance = _set4_saber_required_clearance(source_clip_name)
    if abs(required_clearance - float(SABER_SURFACE_GOAL_CLEARANCE)) > 1.0e-12:
        # Omit the default so the already-proven canonical cache keys remain
        # stable; a tightened equivalence class receives its own identity.
        metadata["required_clearance"] = required_clearance
    required_body_clearance = _set4_saber_required_body_clearance(
        source_clip_name)
    if required_body_clearance > 0.0:
        # Source-scoped collision policies receive their own durable identity,
        # so already-proven unrelated canonical plans remain reusable.
        metadata["required_body_clearance"] = required_body_clearance
        metadata["body_surface_policy"] = (
            SET4_CORE_BODY_SURFACE_POLICY_REVISION)
    return metadata


def _set4_saber_disk_cache_key(metadata):
    import hashlib

    encoded = json.dumps(
        metadata, sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _set4_saber_disk_cache_path(metadata, cache_dir=None):
    directory = pathlib.Path(
        cache_dir if cache_dir is not None else _SET4_SABER_DISK_CACHE_DIR)
    return directory / f"{_set4_saber_disk_cache_key(metadata)}.json"


def _read_set4_saber_disk_plan(metadata, expected_count, cache_dir=None):
    """Read only an exact, finite, correctly shaped checkpoint payload."""
    import math as _math

    if metadata is None:
        return None
    path = _set4_saber_disk_cache_path(metadata, cache_dir)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("metadata") != metadata:
        return None
    if payload.get("cache_key") != _set4_saber_disk_cache_key(metadata):
        return None
    rows = payload.get("corrections")
    report = payload.get("report")
    if not isinstance(rows, list) or len(rows) != int(expected_count):
        return None
    if not isinstance(report, dict):
        return None
    corrections = []
    for row in rows:
        if not isinstance(row, list) or len(row) != 3:
            return None
        try:
            correction = tuple(float(component) for component in row)
        except (TypeError, ValueError):
            return None
        if not all(_math.isfinite(component) for component in correction):
            return None
        corrections.append(correction)
    return tuple(corrections), dict(report)


def _write_set4_saber_disk_plan(
        metadata, corrections, report, cache_dir=None):
    """Atomically checkpoint one already validated canonical plan."""
    if metadata is None:
        return None
    path = _set4_saber_disk_cache_path(metadata, cache_dir)
    payload = {
        "cache_key": _set4_saber_disk_cache_key(metadata),
        "metadata": metadata,
        "corrections": [list(row) for row in corrections],
        "report": dict(report),
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        allow_nan=False)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(encoded, encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        return None
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return path


def _set4_saber_translation_directions():
    """Add 15-degree elevation bridges to the proven clearance lattice.

    The shared lattice samples elevation every 30 degrees.  At long correction
    radii, adjacent branches can be farther apart than a legal 5m/s transition
    even though a continuous path exists between them.  Mid-elevation states
    provide that path without weakening the velocity gate or adding a
    clip-specific exception.
    """
    import math as _math

    result = list(_coupled_defend_translation_directions())
    seen = {
        tuple(round(float(component), 6) for component in direction)
        for direction in result
    }
    for elevation_degrees in (-45, -15, 15, 45):
        elevation = _math.radians(float(elevation_degrees))
        horizontal = _math.cos(elevation)
        vertical = _math.sin(elevation)
        for azimuth_degrees in range(0, 360, 30):
            azimuth = _math.radians(float(azimuth_degrees))
            direction = (
                horizontal * _math.cos(azimuth),
                horizontal * _math.sin(azimuth),
                vertical,
            )
            if direction[1] < -0.55:
                continue
            key = tuple(round(float(component), 6) for component in direction)
            if key not in seen:
                seen.add(key)
                result.append(tuple(float(component) for component in direction))
    return tuple(result)


def _set4_saber_direction_attempts():
    """Return the fast canonical lattice followed by its bridge fallback."""
    return (
        ("base", _coupled_defend_translation_directions()),
        ("bridge_fallback", _set4_saber_translation_directions()),
    )


def _set4_saber_required_clearance(source_clip_name):
    """Return the 60 Hz planning margin for one canonical Set 4 source."""
    source_name = str(source_clip_name or "").strip().lower()
    return float(SET4_SABER_SURFACE_CLEARANCE_BY_SOURCE.get(
        source_name, SABER_SURFACE_GOAL_CLEARANCE))


def _set4_saber_required_body_clearance(source_clip_name):
    """Return the dynamic core-body margin for one canonical source."""
    source_name = str(source_clip_name or "").strip().lower()
    return float(SET4_SABER_BODY_SURFACE_CLEARANCE_BY_SOURCE.get(
        source_name, 0.0))


def _set4_core_body_surface_parts(rigged):
    """Select torso/neck skin faces without pulling animated arms into the hull."""
    import numpy as np
    from src.core.characters.animation_deformation_validator import (
        _skin_rows_to_arrays,
    )

    allowed_bones = {
        "torso_g", "torsoupr_g", "neckbase_g", "neck_g",
        "neckupr_g", "neckupr02_g", "neckupr03_g", "backpack_g",
    }
    parts = []
    face_rows = []
    for part in rigged.all_nodes():
        if (not getattr(part, "is_skin", False)
                or not getattr(part, "vertices", None)):
            continue
        bone_names = [
            str(name or "").strip().lower()
            for name in (getattr(part, "bone_map", None) or [])
        ]
        weights, indices = _skin_rows_to_arrays(
            list(part.skin_data), len(part.vertices), len(bone_names))
        core_weights = np.zeros(len(part.vertices), dtype=np.float64)
        for slot, bone_name in enumerate(bone_names):
            if bone_name in allowed_bones:
                core_weights += np.sum(
                    np.where(indices == int(slot), weights, 0.0), axis=1)
        faces = np.asarray([
            tuple(int(index) for index in face[:3])
            for face in (getattr(part, "faces", None) or [])
            if len(face) >= 3
        ], dtype=np.int64)
        if not len(faces):
            continue
        selected = faces[np.all(core_weights[faces] >= 0.75, axis=1)]
        if len(selected):
            parts.append(part)
            face_rows.append(selected)
    triangle_count = sum(len(rows) for rows in face_rows)
    if triangle_count < 100:
        raise AssertionError(
            f"Set 4 core-body surface is incomplete ({triangle_count} faces)")
    return tuple(parts), tuple(face_rows)


def _set4_core_body_surface_triangles_at_times(anim, rigged, sample_times):
    """Deform the arm-independent body hull at the exact target pose times."""
    import numpy as np
    from src.core.animation.animation_engine import evaluate_aurora_animation_pose

    parts, face_rows = _set4_core_body_surface_parts(rigged)
    result = []
    for time_value in sample_times:
        posed_parts, _world_positions = deformed_parts(
            rigged, parts, str(anim.name), float(time_value))
        pose = evaluate_aurora_animation_pose(
            rigged, anim, float(time_value))
        torso = _pose_world_by_name(pose)["torsoupr_g"]
        chunks = []
        for (vertices, _faces), selected_faces in zip(
                posed_parts, face_rows):
            torso_vertices = np.asarray([
                _point_in_frame(tuple(vertex), torso)
                for vertex in np.asarray(vertices, dtype=np.float64)
            ], dtype=np.float64)
            chunks.append(torso_vertices[selected_faces])
        triangles = np.concatenate(chunks, axis=0)
        if not len(triangles) or not bool(np.isfinite(triangles).all()):
            raise AssertionError(
                f"{anim.name}: invalid dynamic core-body triangle surface")
        result.append(triangles)
    return tuple(result)


def _validate_set4_saber_corrections(
        anim, rigged, source_model, source_clip, solve_times,
        head_triangles_body, corrections, *, body_triangles_by_time=None):
    """Re-prove a checkpoint against the current target before using it."""
    import math as _math
    import numpy as np
    from src.core.animation.animation_engine import evaluate_aurora_animation_pose
    from src.math.limb_ik import solve_two_bone_positions

    if len(corrections) != len(solve_times):
        return None
    required_clearance = _set4_saber_required_clearance(source_clip.name)
    required_body_clearance = _set4_saber_required_body_clearance(
        source_clip.name)
    if required_body_clearance > 0.0:
        if (body_triangles_by_time is None
                or len(body_triangles_by_time) != len(solve_times)):
            return None
    source_cache = {}
    clearances = []
    body_clearances = []
    for solve_index, (time_value, raw_correction) in enumerate(zip(
            solve_times, corrections)):
        correction = np.asarray(raw_correction, dtype=np.float64)
        if correction.shape != (3,) or not bool(np.isfinite(correction).all()):
            return None
        source_time = min(float(source_clip.length), float(time_value))
        source_pose = source_cache.get(source_time)
        if source_pose is None:
            source_pose = evaluate_aurora_animation_pose(
                source_model, source_clip, source_time)
            source_cache[source_time] = source_pose
        source_world = _pose_world_by_name(source_pose)
        target_world = _pose_world_by_name(evaluate_aurora_animation_pose(
            rigged, anim, float(time_value)))
        torso = target_world["torsoupr_g"]
        shoulder = target_world["rbicep_g"]
        elbow = target_world["rforearm_g"]
        hand = target_world["rhand_g"]
        current_hand_body = np.asarray(_point_in_frame(
            hand.position, torso), dtype=np.float64)
        base_goal = np.asarray(_combat_hand_goal_body(
            source_world,
            target_world,
            "r",
            apply_head_clearance=False,
        ), dtype=np.float64)
        projected_goal = np.asarray(_project_hand_goal_outside_torso(
            tuple(float(component) for component in base_goal + correction),
            "r",
        ), dtype=np.float64)
        solution = solve_two_bone_positions(
            shoulder.position,
            elbow.position,
            hand.position,
            _point_from_frame(tuple(projected_goal), torso),
            elbow.position,
        )
        solved_body = np.asarray(_point_in_frame(
            solution.target_position, torso), dtype=np.float64)
        if not _hand_body_outside_torso(solved_body):
            return None
        hand_delta = solved_body - current_hand_body
        blade_start, blade_tip = _right_saber_segment_in_torso(target_world)
        clearance = _segment_triangles_distance(
            blade_start + hand_delta,
            blade_tip + hand_delta,
            head_triangles_body,
        )
        if float(clearance) + 1.0e-9 < required_clearance:
            return None
        clearances.append(float(clearance))
        if required_body_clearance > 0.0:
            body_clearance = _segment_triangles_distance(
                blade_start + hand_delta,
                blade_tip + hand_delta,
                body_triangles_by_time[solve_index],
            )
            if float(body_clearance) + 1.0e-9 < required_body_clearance:
                return None
            body_clearances.append(float(body_clearance))

    jumps = [
        _math.dist(prior, current)
        for prior, current in zip(corrections, corrections[1:])
    ]
    speeds = [
        jump / max(1.0e-5, float(current) - float(prior))
        for jump, prior, current in zip(jumps, solve_times, solve_times[1:])
    ]
    if max(speeds, default=0.0) > (
            float(COUPLED_DEFEND_MAX_CORRECTION_SPEED) + 1.0e-8):
        return None
    report = {
        "validated_min_clearance": min(clearances, default=float("inf")),
        "max_jump": max(jumps, default=0.0),
        "max_speed": max(speeds, default=0.0),
        "max_correction": max(
            (_math.sqrt(sum(float(component) ** 2 for component in correction))
             for correction in corrections),
            default=0.0,
        ),
    }
    if required_body_clearance > 0.0:
        report["validated_min_body_clearance"] = min(body_clearances)
    return report


def _plan_set4_saber_corrections(
        anim, rigged, source_model, source_clip, solve_times,
        head_triangles_body, *, _direction_attempt_index=0,
        _body_triangles_by_time=None):
    """Select a continuous right-hand blade-clear path for one Set 4 motion."""
    import math as _math
    import numpy as np
    from src.core.animation.animation_engine import evaluate_aurora_animation_pose
    from src.math.limb_ik import solve_two_bone_positions

    required_clearance = _set4_saber_required_clearance(source_clip.name)
    required_body_clearance = _set4_saber_required_body_clearance(
        source_clip.name)
    if required_body_clearance > 0.0:
        if _body_triangles_by_time is None:
            _body_triangles_by_time = (
                _set4_core_body_surface_triangles_at_times(
                    anim, rigged, solve_times)
            )
        if len(_body_triangles_by_time) != len(solve_times):
            raise AssertionError(
                f"{anim.name}: core-body surface/time count mismatch")
    disk_metadata = _set4_saber_disk_cache_metadata(
        source_clip.name, solve_times)
    cache_key = (
        "disk",
        _set4_saber_disk_cache_key(disk_metadata),
    ) if disk_metadata is not None else (
        "memory",
        id(rigged),
        str(source_clip.name or "").strip().lower(),
        tuple(round(float(time_value), 7) for time_value in solve_times),
    )
    cached = _SET4_SABER_PLAN_CACHE.get(cache_key)
    if cached is not None:
        validation = _validate_set4_saber_corrections(
            anim,
            rigged,
            source_model,
            source_clip,
            solve_times,
            head_triangles_body,
            cached[0],
            body_triangles_by_time=_body_triangles_by_time,
        )
        if validation is not None:
            return cached
        del _SET4_SABER_PLAN_CACHE[cache_key]

    disk_cached = _read_set4_saber_disk_plan(
        disk_metadata, len(solve_times))
    if disk_cached is not None:
        corrections, report = disk_cached
        policy_rows = dict(_set4_saber_direction_attempts())
        direction_policy = report.get("direction_policy")
        validation = _validate_set4_saber_corrections(
            anim,
            rigged,
            source_model,
            source_clip,
            solve_times,
            head_triangles_body,
            corrections,
            body_triangles_by_time=_body_triangles_by_time,
        )
        if (direction_policy in policy_rows
                and report.get("direction_count") == len(
                    policy_rows[direction_policy])
                and validation is not None):
            report.update(validation)
            report["disk_checkpoint"] = True
            result = (corrections, report)
            _SET4_SABER_PLAN_CACHE[cache_key] = result
            print(
                f"  Set 4 plan checkpoint hit: {source_clip.name} "
                f"({len(corrections)} samples, {direction_policy})")
            return result

    direction_attempts = _set4_saber_direction_attempts()
    direction_policy, direction_rows = direction_attempts[
        int(_direction_attempt_index)]
    directions = tuple(
        np.asarray(direction, dtype=np.float64)
        for direction in direction_rows
    )
    state_lists = []
    source_cache = {}
    state_count_min = 1 << 30
    state_count_max = 0

    for solve_index, time_value in enumerate(solve_times):
        source_time = min(float(source_clip.length), float(time_value))
        source_pose = source_cache.get(source_time)
        if source_pose is None:
            source_pose = evaluate_aurora_animation_pose(
                source_model, source_clip, source_time)
            source_cache[source_time] = source_pose
        source_world = _pose_world_by_name(source_pose)
        target_world = _pose_world_by_name(evaluate_aurora_animation_pose(
            rigged, anim, float(time_value)))
        torso = target_world["torsoupr_g"]
        shoulder = target_world["rbicep_g"]
        elbow = target_world["rforearm_g"]
        hand = target_world["rhand_g"]
        current_hand_body = np.asarray(_point_in_frame(
            hand.position, torso), dtype=np.float64)
        base_goal = np.asarray(_combat_hand_goal_body(
            source_world,
            target_world,
            "r",
            apply_head_clearance=False,
        ), dtype=np.float64)
        blade_start, blade_tip = _right_saber_segment_in_torso(target_world)

        def evaluate(raw_correction):
            correction = np.asarray(raw_correction, dtype=np.float64)
            requested = base_goal + correction
            projected_goal = np.asarray(_project_hand_goal_outside_torso(
                tuple(float(component) for component in requested), "r"),
                dtype=np.float64,
            )
            solution = solve_two_bone_positions(
                shoulder.position,
                elbow.position,
                hand.position,
                _point_from_frame(tuple(projected_goal), torso),
                elbow.position,
            )
            solved_body = np.asarray(_point_in_frame(
                solution.target_position, torso), dtype=np.float64)
            hand_delta = solved_body - current_hand_body
            if not _hand_body_outside_torso(solved_body):
                return None
            clearance = _segment_triangles_distance(
                blade_start + hand_delta,
                blade_tip + hand_delta,
                head_triangles_body,
            )
            body_clearance = float("inf")
            if required_body_clearance > 0.0:
                body_clearance = _segment_triangles_distance(
                    blade_start + hand_delta,
                    blade_tip + hand_delta,
                    _body_triangles_by_time[solve_index],
                )
            return {
                "correction": correction,
                "clearance": float(clearance),
                "body_clearance": float(body_clearance),
                "safe": bool(
                    clearance + 1.0e-9 >= required_clearance
                    and body_clearance + 1.0e-9
                    >= required_body_clearance
                ),
            }

        states_by_cell = {}

        def add_state(raw_correction):
            result = evaluate(raw_correction)
            if result is None or not result["safe"]:
                return
            correction = result["correction"]
            cell = tuple(
                int(round(float(component) / 0.005))
                for component in correction
            )
            prior = states_by_cell.get(cell)
            if prior is None or float(np.linalg.norm(correction)) < float(
                    np.linalg.norm(prior)):
                states_by_cell[cell] = correction

        zero = np.zeros(3, dtype=np.float64)
        base = evaluate(zero)
        if base is not None and base["safe"]:
            add_state(zero)

        # Keep safe continuation states available for the full clip.  Saber
        # orientation can rotate toward the skull faster than centerline
        # distance alone predicts, so a clearance-only anticipation band can
        # open one frame too late for the 5 m/s transition gate.
        needs_lattice = True
        if needs_lattice:
            for direction in directions:
                first_safe = None
                lower = 0.0
                scan_step = 0.03
                scan_count = int(_math.ceil(
                    float(SET4_SABER_FORWARD_SEARCH_LIMIT) / scan_step))
                for index in range(1, scan_count + 1):
                    shift = min(
                        float(SET4_SABER_FORWARD_SEARCH_LIMIT),
                        float(index) * scan_step,
                    )
                    tested = evaluate(direction * shift)
                    if tested is not None and tested["safe"]:
                        upper = shift
                        for _iteration in range(10):
                            midpoint = 0.5 * (lower + upper)
                            mid = evaluate(direction * midpoint)
                            if mid is not None and mid["safe"]:
                                upper = midpoint
                            else:
                                lower = midpoint
                        first_safe = upper
                        break
                    lower = shift
                if first_safe is None:
                    continue
                for continuation in range(11):
                    shift = float(first_safe) + float(continuation) * 0.03
                    if shift <= float(SET4_SABER_FORWARD_SEARCH_LIMIT) + 1.0e-9:
                        add_state(direction * shift)

        if not states_by_cell:
            if int(_direction_attempt_index) + 1 < len(direction_attempts):
                return _plan_set4_saber_corrections(
                    anim,
                    rigged,
                    source_model,
                    source_clip,
                    solve_times,
                    head_triangles_body,
                    _direction_attempt_index=(
                        int(_direction_attempt_index) + 1),
                    _body_triangles_by_time=_body_triangles_by_time,
                )
            fraction = (
                float(time_value) / float(anim.length)
                if float(anim.length) > 1.0e-9 else 0.0)
            raise AssertionError(
                f"{anim.name}: no Set 4 right-saber state at "
                f"{fraction:.1%} (base clearance "
                f"{float(base['clearance']) if base is not None else 0.0:.4f}m)")
        states = np.asarray(sorted(
            states_by_cell.values(),
            key=lambda correction: (
                float(np.linalg.norm(correction)),
                tuple(float(component) for component in correction),
            ),
        ), dtype=np.float64)
        state_lists.append(states)
        state_count_min = min(state_count_min, len(states))
        state_count_max = max(state_count_max, len(states))

    backpointers = []
    previous_states = state_lists[0]
    previous_cost = np.einsum(
        "ij,ij->i", previous_states, previous_states)
    max_speed = float(COUPLED_DEFEND_MAX_CORRECTION_SPEED)
    for index, states in enumerate(state_lists[1:], start=1):
        dt = max(
            1.0e-5,
            float(solve_times[index]) - float(solve_times[index - 1]),
        )
        difference = states[:, None, :] - previous_states[None, :, :]
        distance_sq = np.einsum("ijk,ijk->ij", difference, difference)
        distance = np.sqrt(distance_sq)
        # solve_times contains the 60 Hz lattice plus any authored keys, so
        # ``dt`` is already the strict per-transition bound.  The former
        # additional 0.06m cap rejected valid 3.6-5.0m/s continuations such as
        # f4d2/f2d2 at 54.5%, despite remaining inside the declared 5m/s gate.
        step_limit = max_speed * dt
        transition = np.where(
            distance <= step_limit + 1.0e-9,
            float(COUPLED_DEFEND_VELOCITY_WEIGHT) * distance_sq / dt,
            np.inf,
        )
        total = transition + previous_cost[None, :]
        parents = np.argmin(total, axis=1)
        current_cost = (
            np.einsum("ij,ij->i", states, states) * dt
            + total[np.arange(len(states)), parents]
        )
        if not bool(np.isfinite(current_cost).any()):
            finite_previous = np.isfinite(previous_cost)
            nearest_distance = float("inf")
            nearest_previous = None
            nearest_current = None
            if bool(finite_previous.any()):
                reachable_previous = previous_states[finite_previous]
                pairwise = states[:, None, :] - reachable_previous[None, :, :]
                pairwise_distance = np.sqrt(np.einsum(
                    "ijk,ijk->ij", pairwise, pairwise))
                nearest_flat = int(np.argmin(pairwise_distance))
                nearest_row, nearest_column = np.unravel_index(
                    nearest_flat, pairwise_distance.shape)
                nearest_distance = float(
                    pairwise_distance[nearest_row, nearest_column])
                nearest_previous = tuple(float(component) for component in
                                         reachable_previous[nearest_column])
                nearest_current = tuple(float(component) for component in
                                        states[nearest_row])
            fraction = (
                float(solve_times[index]) / float(anim.length)
                if float(anim.length) > 1.0e-9 else 0.0)
            if int(_direction_attempt_index) + 1 < len(direction_attempts):
                return _plan_set4_saber_corrections(
                    anim,
                    rigged,
                    source_model,
                    source_clip,
                    solve_times,
                    head_triangles_body,
                    _direction_attempt_index=(
                        int(_direction_attempt_index) + 1),
                    _body_triangles_by_time=_body_triangles_by_time,
                )
            raise AssertionError(
                f"{anim.name}: no continuous Set 4 saber path at "
                f"{fraction:.1%} within {max_speed:.1f}m/s; "
                f"nearest {nearest_distance:.5f}m > {step_limit:.5f}m "
                f"over dt={dt:.6f}s, prior={nearest_previous}, "
                f"current={nearest_current}")
        backpointers.append(parents)
        previous_states = states
        previous_cost = current_cost

    selected_indices = [int(np.argmin(previous_cost))]
    for parents in reversed(backpointers):
        selected_indices.append(int(parents[selected_indices[-1]]))
    selected_indices.reverse()
    selected = tuple(
        tuple(float(component) for component in states[index])
        for states, index in zip(state_lists, selected_indices)
    )
    jumps = [
        _math.dist(prior, current)
        for prior, current in zip(selected, selected[1:])
    ]
    speeds = [
        jump / max(1.0e-5, float(current) - float(prior))
        for jump, prior, current in zip(
            jumps, solve_times, solve_times[1:])
    ]
    report = {
        "direction_policy": direction_policy,
        "direction_count": len(direction_rows),
        "required_clearance": required_clearance,
        "required_body_clearance": required_body_clearance,
        "state_count_min": int(state_count_min),
        "state_count_max": int(state_count_max),
        "max_jump": max(jumps, default=0.0),
        "max_speed": max(speeds, default=0.0),
        "max_correction": max(
            (_math.sqrt(sum(component * component for component in correction))
             for correction in selected),
            default=0.0,
        ),
    }
    validation = _validate_set4_saber_corrections(
        anim,
        rigged,
        source_model,
        source_clip,
        solve_times,
        head_triangles_body,
        selected,
        body_triangles_by_time=_body_triangles_by_time,
    )
    assert validation is not None, (
        f"{anim.name}: newly planned Set 4 saber path failed revalidation")
    report.update(validation)
    result = (selected, report)
    _SET4_SABER_PLAN_CACHE[cache_key] = result
    checkpoint_path = _write_set4_saber_disk_plan(
        disk_metadata, selected, report)
    if checkpoint_path is not None:
        print(
            f"  Set 4 plan checkpoint saved: {source_clip.name} "
            f"({len(selected)} samples, {direction_policy})")
    return result


def _solve_set4_right_hand_with_saber_clearance(
        shoulder, elbow, hand, goal_body, pole_world, target_torso,
        blade_segment_body, head_triangles_body,
        previous_correction_body=None, max_correction_step=None,
        planned_correction_body=None, *, body_triangles_body=None,
        required_body_clearance=0.0):
    """Solve one Set 4 saber hand and minimally push its blade forward.

    Set 4 is mostly a one-handed saber vocabulary, so only the saber hand gets
    this collision response.  Its base endpoint remains the Dark Jedi's
    torso-relative endpoint.  Candidate corrections run solely along the
    target torso's forward axis and are tested after target-limb reach
    projection, preserving the left-hand and torso choreography.
    """
    import math as _math
    import numpy as np
    from src.math.limb_ik import solve_two_bone_positions

    base_goal = np.asarray(goal_body, dtype=np.float64)
    current_hand_body = np.asarray(
        _point_in_frame(hand.position, target_torso), dtype=np.float64)
    blade_start, blade_tip = (
        np.asarray(point, dtype=np.float64) for point in blade_segment_body
    )

    def candidate(raw_correction):
        correction = np.asarray(raw_correction, dtype=np.float64)
        requested = base_goal + correction
        projected_goal = np.asarray(_project_hand_goal_outside_torso(
            tuple(float(component) for component in requested), "r"),
            dtype=np.float64,
        )
        solution = solve_two_bone_positions(
            shoulder.position,
            elbow.position,
            hand.position,
            _point_from_frame(tuple(projected_goal), target_torso),
            pole_world,
        )
        solved_body = np.asarray(_point_in_frame(
            solution.target_position, target_torso), dtype=np.float64)
        hand_delta = solved_body - current_hand_body
        clearance = _segment_triangles_distance(
            blade_start + hand_delta,
            blade_tip + hand_delta,
            head_triangles_body,
        )
        body_clearance = float("inf")
        if float(required_body_clearance) > 0.0:
            if body_triangles_body is None:
                raise AssertionError(
                    "Set 4 core-body clearance requires a posed surface")
            body_clearance = _segment_triangles_distance(
                blade_start + hand_delta,
                blade_tip + hand_delta,
                body_triangles_body,
            )
        safe = (
            _hand_body_outside_torso(solved_body)
            and clearance + 1.0e-9
            >= float(SET4_SABER_SURFACE_GOAL_CLEARANCE)
            and body_clearance + 1.0e-9
            >= float(required_body_clearance)
        )
        return {
            "safe": bool(safe),
            "goal_body": tuple(float(component) for component in projected_goal),
            "solution": solution,
            "clearance": float(clearance),
            "body_clearance": float(body_clearance),
            "forward_shift": max(0.0, float(correction[1])),
            "hand_shift": float(np.linalg.norm(correction)),
            "correction_body": tuple(
                float(component) for component in correction),
        }

    zero = np.zeros(3, dtype=np.float64)
    base = candidate(zero)
    planned_reference = None
    if planned_correction_body is not None:
        planned = candidate(planned_correction_body)
        if planned["safe"]:
            return planned
        # A coarse whole-clip path can be safe at both endpoints while its
        # interpolated correction is insufficient for the midpoint pose.
        # Use that interpolated correction as the local continuity guide and
        # search the dense key for the nearest safe neighboring state.
        planned_reference = np.asarray(
            planned_correction_body, dtype=np.float64)

    direction_vectors = tuple(
        np.asarray(direction, dtype=np.float64)
        for direction in _coupled_defend_translation_directions()
    )
    previous = (
        planned_reference
        if planned_reference is not None
        else np.asarray(previous_correction_body, dtype=np.float64)
        if previous_correction_body is not None else zero
    )
    step = float(SET4_SABER_FORWARD_SEARCH_STEP)
    count = int(_math.ceil(
        float(SET4_SABER_FORWARD_SEARCH_LIMIT) / step))
    step_limit = (
        float(max_correction_step)
        if max_correction_step is not None else float("inf")
    )

    def continuous(tested):
        return (
            previous_correction_body is None
            or float(np.linalg.norm(
                np.asarray(tested["correction_body"], dtype=np.float64)
                - previous
            )) <= step_limit + 1.0e-9
        )

    safe_candidates = [base] if base["safe"] and continuous(base) else []
    previous_test = candidate(previous)
    if previous_test["safe"] and continuous(previous_test):
        safe_candidates.append(previous_test)
    first_safe_radius = 0.0 if safe_candidates else None
    continuation_radius = max(
        float(np.linalg.norm(previous)) + 0.045,
        0.15,
    )
    for index in range(1, count + 1):
        shift = min(
            float(SET4_SABER_FORWARD_SEARCH_LIMIT),
            float(index) * step,
        )
        for direction in direction_vectors:
            tested = candidate(direction * shift)
            if tested["safe"] and continuous(tested):
                safe_candidates.append(tested)
                if first_safe_radius is None:
                    first_safe_radius = shift
        if (first_safe_radius is not None
                and shift >= max(
                    first_safe_radius + 0.15,
                    continuation_radius,
                )):
            break
    if not safe_candidates:
        raise AssertionError(
            "Set 4 right-saber goal has no blade-clear solution "
            f"within {SET4_SABER_FORWARD_SEARCH_LIMIT:.2f}m "
            f"and continuity step {step_limit:.4f}m "
            f"(base head {base['clearance']:.4f}m, body "
            f"{base['body_clearance']:.4f}m)")
    # Greedy continuity is sufficient at the 60 Hz authored lattice and much
    # lighter than the old whole-clip two-hand Viterbi planner.  Magnitude
    # still wins over time, while an eightfold change penalty prevents a
    # symmetric left/right branch flip from sweeping the blade through the
    # head between adjacent keys.
    return min(
        safe_candidates,
        key=lambda tested: (
            float(np.linalg.norm(tested["correction_body"])) ** 2
            + 8.0 * float(np.linalg.norm(
                np.asarray(tested["correction_body"], dtype=np.float64)
                - previous
            )) ** 2,
            -float(tested["forward_shift"]),
            tuple(float(component) for component in tested["correction_body"]),
        ),
    )


def retarget_combat_arm_position_goals(anim, rigged, source_model, source_clip_name):
    """Bake torso-relative two-bone IK for the Ithorian combat arms (T2568).

    Humanoid rotations remain the base motion.  This post-pass transfers the
    donor's hand ENDPOINT in animated ``torsoUpr_g`` space, analytically solves
    bicep+forearm for the target limb lengths, and adds a compensating hand key
    so the already-retargeted saber orientation does not change.
    """
    import math as _math
    from src.core.animation.animation_engine import evaluate_aurora_animation_pose
    from src.math.limb_ik import solve_two_bone_positions

    source_clip = next(
        a for a in source_model.animations
        if str(a.name or "").strip().lower() == source_clip_name.lower()
    )
    length = max(0.0, float(getattr(anim, "length", 0.0) or 0.0))
    clip_name = str(getattr(anim, "name", "") or "").strip().lower()
    uses_coupled_surface = _uses_coupled_saber_surface_goal(
        clip_name, source_clip_name)
    uses_set4_surface = _uses_set4_saber_surface_goal(
        clip_name, source_clip_name)
    required_set4_body_clearance = (
        _set4_saber_required_body_clearance(source_clip.name)
        if uses_set4_surface else 0.0
    )
    relevant_names = {
        "torsoupr_g", "head_g",
        "rbicep_g", "rforearm_g", "rhand_g",
        "lbicep_g", "lforearm_g", "lhand_g",
    }
    original_times = [0.0, length]
    for block in (anim, source_clip):
        for node in block.nodes or []:
            if str(node.name or "").strip().lower() not in relevant_names:
                continue
            for ctrl in node.controllers or []:
                original_times.extend(float(t) for t in (ctrl.get("times") or []))
    original_times = _clean_animation_times(original_times, length)
    solve_rate = (
        float(COUPLED_BAKE_RATE_BY_CLIP.get(clip_name, 240.0))
        if uses_coupled_surface
        else float(SET4_ARM_BAKE_RATE_BY_SOURCE.get(
            str(source_clip_name or "").strip().lower(),
            SET4_ARM_BAKE_RATE,
        )) if uses_set4_surface
        else 30.0
    )
    apply_rate = float(COUPLED_APPLY_RATE_BY_CLIP.get(
        clip_name, solve_rate))
    solve_times = [] if uses_coupled_surface else list(original_times)
    for index in range(int(_math.floor(length * solve_rate)) + 1):
        candidate = index / solve_rate
        if all(abs(candidate - existing) > 1.0e-4 for existing in solve_times):
            solve_times.append(candidate)
    if (uses_set4_surface
            and str(source_clip_name or "").strip().lower()
            in MALAK_DIRECT_GREEDY_SABER_SOURCES):
        # Preserve the exact review witnesses as authored IK keys. Several
        # clip lengths put 40%/60%/80% between the regular samples, where
        # quaternion interpolation can otherwise re-enter the head or torso.
        solve_times.extend(
            length * fraction
            for fraction in SET4_BODY_SURFACE_REVIEW_FRACTIONS
        )
    solve_times = _clean_animation_times(solve_times + [length], length)
    apply_times = solve_times
    if uses_coupled_surface:
        plan_rate = float(COUPLED_PLAN_RATE_BY_CLIP.get(clip_name, 120.0))
        plan_times = [
            index / plan_rate
            for index in range(int(_math.floor(length * plan_rate)) + 1)
        ]
        plan_times = _clean_animation_times(plan_times + [length], length)
        path_rate = float(COUPLED_PATH_RATE_BY_CLIP.get(
            clip_name, solve_rate))
        path_times = [
            index / path_rate
            for index in range(int(_math.floor(length * path_rate)) + 1)
        ]
        path_times = _clean_animation_times(path_times + [length], length)
    else:
        plan_times = solve_times
        path_times = solve_times

    tracks = {}
    rig_by_name = {
        str(node.name or "").strip().lower(): node for node in rigged.all_nodes()
    }
    for side in ("r", "l"):
        for role in ("bicep", "forearm", "hand"):
            name = f"{side}{role}_g"
            tracks[name] = _ensure_arm_orientation_track(anim, rigged, name, solve_times)

    source_cache = {}
    projected = 0
    solved_keys = 0
    max_residual = 0.0
    max_landing_error = 0.0
    max_elbow_pole_bias = 0.0
    max_saber_forward_shift = 0.0
    max_saber_hand_shift = 0.0
    min_saber_surface_clearance = float("inf")
    min_saber_body_clearance = float("inf")
    min_left_elbow_gap = float("inf")
    head_triangles_body = (
        _head_surface_triangles_in_torso_space(anim, rigged)
        if uses_coupled_surface or uses_set4_surface else None
    )
    set4_saber_corrections = None
    set4_saber_plan = None
    uses_direct_greedy_saber = bool(
        uses_set4_surface
        and str(source_clip_name or "").strip().lower()
        in MALAK_DIRECT_GREEDY_SABER_SOURCES
    )
    set4_body_triangles_by_time = None
    if required_set4_body_clearance > 0.0:
        set4_body_triangles_by_time = (
            _set4_core_body_surface_triangles_at_times(
                anim, rigged, solve_times)
        )
    if uses_set4_surface:
        plan_solve_times = solve_times
        plan_body_triangles = set4_body_triangles_by_time
        if uses_direct_greedy_saber:
            guide_rate = (
                30.0
                if str(source_clip_name or "").strip().lower() == "c2a3"
                else 60.0
            )
            plan_solve_times = _clean_animation_times(
                list(original_times) + [
                    index / guide_rate
                    for index in range(int(_math.floor(length * guide_rate)) + 1)
                ] + [length],
                length,
            )
            plan_body_triangles = None
        set4_saber_corrections, set4_saber_plan = (
            _plan_set4_saber_corrections(
                anim,
                rigged,
                source_model,
                source_clip,
                plan_solve_times,
                head_triangles_body,
                _body_triangles_by_time=plan_body_triangles,
            )
        )
        if uses_direct_greedy_saber:
            set4_saber_corrections = _resample_delta_path(
                plan_solve_times,
                set4_saber_corrections,
                solve_times,
                spherical=False,
            )
    previous_set4_saber_correction = None
    previous_set4_bend_body = {"r": None, "l": None}
    for key_index, time_value in enumerate(solve_times):
        fraction = 1.0 if length <= 1.0e-9 else float(time_value) / length
        source_time = min(float(source_clip.length), float(time_value))
        source_pose = source_cache.get(source_time)
        if source_pose is None:
            source_pose = evaluate_aurora_animation_pose(
                source_model, source_clip, source_time)
            source_cache[source_time] = source_pose
        source_world = _pose_world_by_name(source_pose)

        for side in ("r", "l"):
            if (side == "l" and uses_set4_surface
                    and str(source_clip_name or "").strip().lower()
                    in MALAK_RIGHT_ARM_ONLY_SURFACE_SOURCES):
                continue
            target_pose = evaluate_aurora_animation_pose(rigged, anim, time_value)
            target_world = _pose_world_by_name(target_pose)
            required = (
                "torsoupr_g", f"{side}bicep_g", f"{side}forearm_g",
                f"{side}hand_g",
            )
            if any(name not in source_world for name in required):
                raise AssertionError(f"{anim.name}: source arm chain missing for {side}")
            if any(name not in target_world for name in required):
                raise AssertionError(f"{anim.name}: target arm chain missing for {side}")

            shoulder = target_world[f"{side}bicep_g"]
            elbow = target_world[f"{side}forearm_g"]
            hand = target_world[f"{side}hand_g"]
            original_hand_world_q = tuple(float(c) for c in hand.rotation[:4])
            goal_body = _combat_hand_goal_body(
                source_world,
                target_world,
                side,
                apply_head_clearance=not (
                    uses_coupled_surface or uses_set4_surface),
            )
            if uses_set4_surface:
                prior_bend_direction = previous_set4_bend_body[side]
                pole_body, bend_direction, _source_bend_ratio = (
                    _retarget_set4_elbow_pole_body(
                        source_world,
                        target_world,
                        side,
                        goal_body,
                        prior_bend_direction,
                    )
                )
            else:
                pole_body = _point_in_frame(
                    source_world[f"{side}forearm_g"].position,
                    source_world["torsoupr_g"],
                )
            if (not uses_set4_surface
                    and clip_name == "c2a1" and side == "l"):
                # The donor's mid-swing left-elbow pole is technically below
                # the wrist but leaves too little visible separation on the
                # long Ithorian arm.  Lower only the bend pole through the
                # middle of the attack; the hand goal and two-handed grip stay
                # fixed, and the bias returns smoothly to zero where the
                # 70%-90% endpoint-guard overlay begins.
                pole_weight = _transient_hold_weight(
                    fraction, 0.45, 0.52, 0.62, 0.70)
                pole_bias = 0.04 * pole_weight
                pole_body = (
                    pole_body[0],
                    pole_body[1],
                    pole_body[2] - pole_bias,
                )
                max_elbow_pole_bias = max(max_elbow_pole_bias, pole_bias)
            pole_world = _point_from_frame(
                pole_body, target_world["torsoupr_g"])
            if uses_set4_surface and side == "r":
                blade_result = _solve_set4_right_hand_with_saber_clearance(
                    shoulder,
                    elbow,
                    hand,
                    goal_body,
                    pole_world,
                    target_world["torsoupr_g"],
                    _right_saber_segment_in_torso(target_world),
                    head_triangles_body,
                    previous_set4_saber_correction,
                    (
                        None
                        if uses_direct_greedy_saber
                        else SET4_SABER_MAX_CORRECTION_STEP
                        if previous_set4_saber_correction is not None else None
                    ),
                    set4_saber_corrections[key_index],
                    body_triangles_body=(
                        set4_body_triangles_by_time[key_index]
                        if set4_body_triangles_by_time is not None else None
                    ),
                    required_body_clearance=required_set4_body_clearance,
                )
                previous_set4_saber_correction = tuple(
                    blade_result["correction_body"])
                goal_body = blade_result["goal_body"]
                # The collision search only needs the endpoint and can ignore
                # the elbow plane.  Re-project the donor bend direction into
                # the selected shoulder-to-goal plane before the final solve.
                pole_body, bend_direction, _source_bend_ratio = (
                    _retarget_set4_elbow_pole_body(
                        source_world,
                        target_world,
                        side,
                        goal_body,
                        prior_bend_direction,
                    )
                )
                previous_set4_bend_body[side] = tuple(
                    float(component) for component in bend_direction)
                pole_world = _point_from_frame(
                    pole_body, target_world["torsoupr_g"])
                solution = solve_two_bone_positions(
                    shoulder.position,
                    elbow.position,
                    hand.position,
                    _point_from_frame(
                        goal_body, target_world["torsoupr_g"]),
                    pole_world,
                )
                max_saber_forward_shift = max(
                    max_saber_forward_shift,
                    float(blade_result["forward_shift"]),
                )
                max_saber_hand_shift = max(
                    max_saber_hand_shift,
                    float(blade_result["hand_shift"]),
                )
                min_saber_surface_clearance = min(
                    min_saber_surface_clearance,
                    float(blade_result["clearance"]),
                )
                min_saber_body_clearance = min(
                    min_saber_body_clearance,
                    float(blade_result["body_clearance"]),
                )
            elif clip_name in LOW_LEFT_ELBOW_GOAL_CLIPS and side == "l":
                goal_world = _point_from_frame(
                    goal_body, target_world["torsoupr_g"])
                solution, pole_world, pole_bias, elbow_gap = (
                    _solve_with_lower_left_elbow(
                        shoulder,
                        elbow,
                        hand,
                        goal_world,
                        pole_world,
                    )
                )
                max_elbow_pole_bias = max(
                    max_elbow_pole_bias, float(pole_bias))
                min_left_elbow_gap = min(
                    min_left_elbow_gap, float(elbow_gap))
            else:
                if uses_set4_surface:
                    previous_set4_bend_body[side] = tuple(
                        float(component) for component in bend_direction)
                goal_world = _point_from_frame(
                    goal_body, target_world["torsoupr_g"])
                solution = solve_two_bone_positions(
                    shoulder.position,
                    elbow.position,
                    hand.position,
                    goal_world,
                    pole_world,
                )
            projected += int(not solution.reached)
            max_residual = max(max_residual, float(solution.residual))

            shoulder_delta = _quat_between_vecs(
                tuple(float(a) - float(b) for a, b in zip(elbow.position, shoulder.position)),
                tuple(float(a) - float(b) for a, b in zip(
                    solution.elbow_position, shoulder.position)),
            )
            new_shoulder_world = _quat_norm_xyzw(_quat_mul_xyzw(
                shoulder_delta, tuple(float(c) for c in shoulder.rotation[:4])))
            shoulder_parent = rig_by_name[f"{side}bicep_g"].parent
            parent_world = target_world[str(shoulder_parent.name).strip().lower()]
            tracks[f"{side}bicep_g"]["values"][key_index] = list(
                _quat_norm_xyzw(_quat_mul_xyzw(
                    _quat_inv_xyzw(tuple(float(c) for c in parent_world.rotation[:4])),
                    new_shoulder_world,
                )))

            target_pose = evaluate_aurora_animation_pose(rigged, anim, time_value)
            target_world = _pose_world_by_name(target_pose)
            elbow = target_world[f"{side}forearm_g"]
            hand = target_world[f"{side}hand_g"]
            elbow_delta = _quat_between_vecs(
                tuple(float(a) - float(b) for a, b in zip(hand.position, elbow.position)),
                tuple(float(a) - float(b) for a, b in zip(
                    solution.target_position, elbow.position)),
            )
            new_elbow_world = _quat_norm_xyzw(_quat_mul_xyzw(
                elbow_delta, tuple(float(c) for c in elbow.rotation[:4])))
            elbow_parent = rig_by_name[f"{side}forearm_g"].parent
            parent_world = target_world[str(elbow_parent.name).strip().lower()]
            tracks[f"{side}forearm_g"]["values"][key_index] = list(
                _quat_norm_xyzw(_quat_mul_xyzw(
                    _quat_inv_xyzw(tuple(float(c) for c in parent_world.rotation[:4])),
                    new_elbow_world,
                )))

            # Preserve the world hand/saber rotation from the already-correct
            # orientation retarget while the two IK joints move its position.
            target_pose = evaluate_aurora_animation_pose(rigged, anim, time_value)
            target_world = _pose_world_by_name(target_pose)
            hand_parent = rig_by_name[f"{side}hand_g"].parent
            parent_world = target_world[str(hand_parent.name).strip().lower()]
            tracks[f"{side}hand_g"]["values"][key_index] = list(
                _quat_norm_xyzw(_quat_mul_xyzw(
                    _quat_inv_xyzw(tuple(float(c) for c in parent_world.rotation[:4])),
                    original_hand_world_q,
                )))

            target_pose = evaluate_aurora_animation_pose(rigged, anim, time_value)
            solved_hand = _pose_world_by_name(target_pose)[f"{side}hand_g"]
            landing_error = _math.sqrt(sum(
                (float(a) - float(b)) ** 2
                for a, b in zip(solved_hand.position, solution.target_position)
            ))
            max_landing_error = max(max_landing_error, landing_error)
            if landing_error > 1.0e-3:
                raise AssertionError(
                    f"{anim.name} {side}hand IK miss at {time_value:.5f}: "
                    f"{landing_error:.6f}m")
            solved_keys += 3

    coupled_report = None
    coupled_path_report = None
    dense_grip_baseline = ()
    if uses_coupled_surface:
        dense_grip_times = [
            index / (apply_rate * 2.0)
            for index in range(int(_math.floor(length * apply_rate * 2.0)) + 1)
        ]
        dense_grip_times = _clean_animation_times(
            dense_grip_times + list(solve_times) + [length], length)
        dense_grip_baseline = _sample_torso_grip_vectors(
            anim, rigged, dense_grip_times)
        selected_deltas, plan_report = _plan_coupled_defend_deltas(
            anim,
            rigged,
            plan_times,
            head_triangles_body,
            clearance=float(SABER_SURFACE_CLEARANCE_BY_CLIP.get(
                clip_name, SABER_SURFACE_GOAL_CLEARANCE)),
        )
        path_deltas = _resample_delta_path(
            plan_times,
            selected_deltas,
            path_times,
            spherical=False,
        )
        if clip_name in COUPLED_CONTINUATION_CLEARANCE_BY_CLIP:
            path_deltas, coupled_path_report = _refine_coupled_defend_delta_path(
                anim,
                rigged,
                path_times,
                path_deltas,
                head_triangles_body,
                clearance=float(
                    COUPLED_CONTINUATION_CLEARANCE_BY_CLIP[clip_name]),
                beam_width=int(COUPLED_CONTINUATION_BEAM_WIDTH_BY_CLIP.get(
                    clip_name, COUPLED_CONTINUATION_BEAM_WIDTH)),
                # c2d3 needs the complete clip to return from its skull
                # detour.  A nearby padded guide anchor prunes every otherwise
                # safe branch around 80%; the authored final key remains the
                # mandatory exact anchor while all 5m/s and collision gates
                # continue to apply at every transition substep.
                window_padding_after=(
                    len(path_times)
                    if clip_name in COUPLED_CONTINUATION_END_ANCHOR_CLIPS
                    else None
                ),
            )
        else:
            path_audit = audit_coupled_defend_delta_path(
                anim,
                rigged,
                path_times,
                path_deltas,
                head_triangles_body,
                include_midpoints=True,
            )
            coupled_path_report = {
                "refined": False,
                "bad_samples": 0,
                "window_start": 0,
                "window_end": 0,
                "expanded_candidates": 0,
                "accepted_candidates": 0,
                "audit": path_audit,
            }
        bake_deltas = _resample_delta_path(
            path_times,
            path_deltas,
            solve_times,
            spherical=False,
        )
        # Re-audit the exact denser trajectory that will be converted into IK
        # keys.  c2d2 searches at 240 Hz but serializes at 480 Hz; checking the
        # 25/50/75% probes here gives 1,920 Hz target-path coverage before FK.
        bake_path_audit = audit_coupled_defend_delta_path(
            anim,
            rigged,
            solve_times,
            bake_deltas,
            head_triangles_body,
            include_midpoints=True,
            transition_substeps=4,
        )
        minimum_path_clearance = float(
            COUPLED_CONTINUATION_CLEARANCE_BY_CLIP.get(
                clip_name, RIGHT_SABER_HEAD_CLEARANCE_MIN))
        dense_refine_report = None
        dense_path_is_safe = (
            bake_path_audit["max_speed"]
            <= float(COUPLED_DEFEND_MAX_CORRECTION_SPEED) + 1.0e-6
            and bake_path_audit["min_clearance"] + 1.0e-9
            >= minimum_path_clearance
            and not bake_path_audit["torso_violations"]
            and not bake_path_audit["reach_violations"]
        )
        if (not dense_path_is_safe
                and clip_name in COUPLED_CONTINUATION_CLEARANCE_BY_CLIP
                and tuple(path_times) != tuple(solve_times)):
            # The 240 Hz route can be valid at quarter-substeps while the
            # denser 480 Hz base-arm curve exposes a smaller nonlinear unsafe
            # interval.  Repair only that resampled neighborhood on the bake
            # lattice; its quarter probes are the same 1,920 Hz gate below.
            bake_deltas, dense_refine_report = (
                _refine_coupled_defend_delta_path(
                    anim,
                    rigged,
                    solve_times,
                    bake_deltas,
                    head_triangles_body,
                    clearance=minimum_path_clearance,
                    window_padding_before=(
                        int(COUPLED_CONTINUATION_WINDOW_PADDING) * 2),
                    # The cached route is already at the 5m/s limit while it
                    # returns from the skull detour.  Give the dense repair the
                    # remaining clip to merge back, while its final guide key
                    # stays a mandatory exact end-guard anchor.
                    window_padding_after=len(solve_times),
                    transition_substeps=4,
                )
            )
            bake_path_audit = dense_refine_report["audit"]
        if bake_path_audit["max_speed"] > (
                float(COUPLED_DEFEND_MAX_CORRECTION_SPEED) + 1.0e-6):
            raise AssertionError(
                f"{anim.name}: baked correction moves at "
                f"{bake_path_audit['max_speed']:.3f}m/s")
        if (bake_path_audit["min_clearance"] + 1.0e-9
                < minimum_path_clearance):
            raise AssertionError(
                f"{anim.name}: baked blade/head clearance is "
                f"{bake_path_audit['min_clearance']:.4f}m")
        if (bake_path_audit["torso_violations"]
                or bake_path_audit["reach_violations"]):
            raise AssertionError(
                f"{anim.name}: baked path has "
                f"{bake_path_audit['torso_violations']} torso and "
                f"{bake_path_audit['reach_violations']} reach violations")
        search_audit = coupled_path_report.get("audit")
        coupled_path_report["search_audit"] = search_audit
        coupled_path_report["dense_refine"] = dense_refine_report
        coupled_path_report["bake_audit"] = bake_path_audit

        apply_times = [
            index / apply_rate
            for index in range(int(_math.floor(length * apply_rate)) + 1)
        ]
        apply_times = _clean_animation_times(
            apply_times + [length], length)
        apply_deltas = _resample_delta_path(
            solve_times,
            bake_deltas,
            apply_times,
            spherical=False,
        )
        if tuple(apply_times) != tuple(solve_times):
            # Resample the immutable pre-coupled arm curves before writing any
            # shared-delta keys.  New midpoint solves must never use an already
            # broken coupled interpolation as their baseline.
            for side in ("r", "l"):
                for role in ("bicep", "forearm", "hand"):
                    name = f"{side}{role}_g"
                    tracks[name] = _ensure_arm_orientation_track(
                        anim, rigged, name, apply_times)
        apply_path_audit = audit_coupled_defend_delta_path(
            anim,
            rigged,
            apply_times,
            apply_deltas,
            head_triangles_body,
            include_midpoints=True,
            transition_substeps=2,
        )
        if (apply_path_audit["max_speed"]
                > float(COUPLED_DEFEND_MAX_CORRECTION_SPEED) + 1.0e-6
                or apply_path_audit["min_clearance"] + 1.0e-9
                < minimum_path_clearance
                or apply_path_audit["torso_violations"]
                or apply_path_audit["reach_violations"]):
            raise AssertionError(
                f"{anim.name}: applied-key target path failed: "
                f"speed={apply_path_audit['max_speed']:.3f}m/s "
                f"clearance={apply_path_audit['min_clearance']:.4f}m "
                f"torso={apply_path_audit['torso_violations']} "
                f"reach={apply_path_audit['reach_violations']}")
        coupled_path_report["audit"] = apply_path_audit
        coupled_report = _apply_coupled_defend_deltas(
            anim,
            rigged,
            apply_times,
            tracks,
            rig_by_name,
            apply_deltas,
        )
        actual_max_shift = max(
            (float(_math.sqrt(sum(float(component) ** 2
                                  for component in delta)))
             for delta in apply_deltas),
            default=0.0,
        )
        max_saber_forward_shift = max(
            max_saber_forward_shift, actual_max_shift)
        max_saber_hand_shift = max(
            max_saber_hand_shift, actual_max_shift)
        min_saber_surface_clearance = min(
            min_saber_surface_clearance,
            float(coupled_path_report["audit"]["min_clearance"]),
        )
        max_landing_error = max(
            max_landing_error,
            float(coupled_report["max_landing_error"]),
        )
        max_elbow_pole_bias = max(
            max_elbow_pole_bias,
            float(coupled_report["max_elbow_pole_bias"]),
        )

    for ctrl in tracks.values():
        _restore_orientation_continuity(ctrl)
    dense_grip_audit = (
        audit_grip_against_baseline(anim, rigged, dense_grip_baseline)
        if dense_grip_baseline else {
            "samples": 0,
            "max_grip_vector_error": 0.0,
            "max_time": 0.0,
            "max_fraction": 0.0,
        }
    )
    dense_grip_limit = float(
        COUPLED_GRIP_DRIFT_LIMIT_BY_CLIP.get(clip_name, 0.01))
    if dense_grip_audit["max_grip_vector_error"] > dense_grip_limit:
        raise AssertionError(
            f"{anim.name}: coupled interpolation changed the two-hand grip by "
            f"{dense_grip_audit['max_grip_vector_error']:.4f}m at "
            f"{dense_grip_audit['max_fraction']:.1%} "
            f"(limit {dense_grip_limit:.4f}m)")
    return {
        "solve_times": len(solve_times),
        "apply_times": len(apply_times),
        "keys": solved_keys,
        "projected": projected,
        "max_projection": max_residual,
        "max_landing_error": max_landing_error,
        "max_elbow_pole_bias": max_elbow_pole_bias,
        "max_saber_forward_shift": max_saber_forward_shift,
        "max_saber_hand_shift": max_saber_hand_shift,
        "min_saber_surface_clearance": min_saber_surface_clearance,
        "min_saber_body_clearance": min_saber_body_clearance,
        "min_left_elbow_gap": min_left_elbow_gap,
        "coupled_plan": plan_report if coupled_report is not None else None,
        "coupled_path": coupled_path_report,
        "max_grip_vector_error": (
            float(coupled_report["max_grip_vector_error"])
            if coupled_report is not None else 0.0),
        "dense_grip_baseline": dense_grip_baseline,
        "dense_grip_audit": dense_grip_audit,
        "coupled_surface": bool(uses_coupled_surface),
        "set4_surface": bool(uses_set4_surface),
        "set4_saber_plan": set4_saber_plan,
    }


def audit_combat_arm_position_goals(
        anim, rigged, source_model, source_clip_name, *,
        ignore_endpoint_goal=False, start_fraction=0.0, end_fraction=1.0,
        exclude_fraction_ranges=(), skip_position_goals=False):
    """Measure the serialized limb solve against its torso-space donor goals."""
    import math as _math
    from src.core.animation.animation_engine import evaluate_aurora_animation_pose
    from src.math.limb_ik import solve_two_bone_positions

    source_clip = next(
        a for a in source_model.animations
        if str(a.name or "").strip().lower() == source_clip_name.lower()
    )
    length = float(anim.length)
    start_time = length * max(0.0, min(1.0, float(start_fraction)))
    end_time = length * max(0.0, min(1.0, float(end_fraction)))
    if end_time < start_time:
        start_time, end_time = end_time, start_time
    sample_times = [
        index / 30.0
        for index in range(
            int(_math.floor(start_time * 30.0)),
            int(_math.ceil(end_time * 30.0)) + 1,
        )
        if start_time <= index / 30.0 <= end_time
    ]
    sample_times = _clean_animation_times(
        sample_times + [start_time, end_time], length)
    excluded = [
        (
            length * max(0.0, min(1.0, float(start))),
            length * max(0.0, min(1.0, float(end))),
        )
        for start, end in exclude_fraction_ranges
    ]
    excluded = [
        (min(start, end), max(start, end)) for start, end in excluded
    ]
    if excluded:
        sample_times = [
            time_value for time_value in sample_times
            if not any(
                range_start <= time_value <= range_end
                for range_start, range_end in excluded
            )
        ]
    max_landing_error = 0.0
    goal_samples = 0
    torso_violations = 0
    for time_value in sample_times:
        source_pose = evaluate_aurora_animation_pose(
            source_model, source_clip, min(float(source_clip.length), time_value))
        target_pose = evaluate_aurora_animation_pose(rigged, anim, time_value)
        source_world = _pose_world_by_name(source_pose)
        target_world = _pose_world_by_name(target_pose)
        target_torso = target_world["torsoupr_g"]
        for side in ("r", "l"):
            hand = target_world[f"{side}hand_g"]
            measure_goal = (
                not skip_position_goals
                and not (
                    ignore_endpoint_goal
                    and abs(float(time_value) - length) <= 1.0e-5)
            )
            if measure_goal:
                goal_body = _combat_hand_goal_body(source_world, target_world, side)
                goal_world = _point_from_frame(goal_body, target_torso)
                source_elbow_body = _point_in_frame(
                    source_world[f"{side}forearm_g"].position,
                    source_world["torsoupr_g"],
                )
                pole_world = _point_from_frame(source_elbow_body, target_torso)
                shoulder = target_world[f"{side}bicep_g"]
                elbow = target_world[f"{side}forearm_g"]
                expected = solve_two_bone_positions(
                    shoulder.position, elbow.position, hand.position,
                    goal_world, pole_world)
                max_landing_error = max(
                    max_landing_error,
                    _math.dist(hand.position, expected.target_position),
                )
                goal_samples += 1
            hx, hy, _hz = _point_in_frame(hand.position, target_torso)
            radius = _math.hypot(hx, hy + 0.05)
            torso_violations += int(
                hy < -0.33 or (hy < 0.17 and radius < 0.39))

    end_pose = evaluate_aurora_animation_pose(rigged, anim, length)
    end_world = _pose_world_by_name(end_pose)
    end_torso = end_world["torsoupr_g"]
    head_y = _point_in_frame(end_world["head_g"].position, end_torso)[1]
    saber_socket_y = _point_in_frame(end_world["rhand"].position, end_torso)[1]
    return {
        "samples": len(sample_times),
        "goal_samples": goal_samples,
        "max_landing_error": max_landing_error,
        "torso_violations": torso_violations,
        "saber_head_clearance": saber_socket_y - head_y,
    }


def audit_elbow_below_wrist(
        anim, rigged, side, *, start_fraction, end_fraction,
        extra_fractions=(), sample_rate=30.0):
    """Measure world-vertical wrist clearance above one elbow at 30 Hz."""
    import math as _math
    from src.core.animation.animation_engine import evaluate_aurora_animation_pose

    length = max(0.0, float(getattr(anim, "length", 0.0) or 0.0))
    start = length * max(0.0, min(1.0, float(start_fraction)))
    end = length * max(0.0, min(1.0, float(end_fraction)))
    if end < start:
        start, end = end, start
    sample_times = [
        index / float(sample_rate)
        for index in range(
            int(_math.floor(start * float(sample_rate))),
            int(_math.ceil(end * float(sample_rate))) + 1,
        )
        if start <= index / float(sample_rate) <= end
    ]
    sample_times.extend(
        length * max(0.0, min(1.0, float(fraction)))
        for fraction in extra_fractions
    )
    sample_times = _clean_animation_times(sample_times + [start, end], length)
    gaps = []
    for time_value in sample_times:
        world = _pose_world_by_name(evaluate_aurora_animation_pose(
            rigged, anim, time_value))
        elbow = world[f"{side}forearm_g"]
        wrist = world[f"{side}hand_g"]
        gaps.append(float(wrist.position[2]) - float(elbow.position[2]))
    return {
        "samples": len(sample_times),
        "min_wrist_above_elbow": min(gaps) if gaps else float("inf"),
    }


def audit_coupled_grip_vector(
        anim, rigged, source_model, source_clip_name, *, sample_rate=120.0,
        extra_fractions=()):
    """Measure two-hand grip preservation against the uncoupled donor goals."""
    import math as _math
    import numpy as np
    from src.core.animation.animation_engine import evaluate_aurora_animation_pose
    from src.math.limb_ik import solve_two_bone_positions

    source_clip = next(
        candidate for candidate in source_model.animations
        if str(candidate.name or "").strip().lower()
        == str(source_clip_name).strip().lower()
    )
    length = max(0.0, float(getattr(anim, "length", 0.0) or 0.0))
    sample_times = [
        index / float(sample_rate)
        for index in range(int(_math.floor(length * float(sample_rate))) + 1)
    ]
    sample_times.extend(
        length * max(0.0, min(1.0, float(fraction)))
        for fraction in extra_fractions
    )
    sample_times = _clean_animation_times(sample_times + [length], length)
    max_error = 0.0
    max_time = 0.0
    for time_value in sample_times:
        source_pose = evaluate_aurora_animation_pose(
            source_model,
            source_clip,
            min(float(source_clip.length), float(time_value)),
        )
        target_pose = evaluate_aurora_animation_pose(
            rigged, anim, float(time_value))
        source_world = _pose_world_by_name(source_pose)
        target_world = _pose_world_by_name(target_pose)
        target_torso = target_world["torsoupr_g"]
        actual = {
            side: np.asarray(_point_in_frame(
                target_world[f"{side}hand_g"].position, target_torso),
                dtype=np.float64,
            )
            for side in ("r", "l")
        }
        expected = {}
        for side in ("r", "l"):
            goal_body = _combat_hand_goal_body(
                source_world,
                target_world,
                side,
                apply_head_clearance=(
                    str(anim.name or "").strip().lower()
                    not in SABER_SURFACE_GOAL_CLIPS
                ),
            )
            goal_world = _point_from_frame(goal_body, target_torso)
            source_elbow_body = _point_in_frame(
                source_world[f"{side}forearm_g"].position,
                source_world["torsoupr_g"],
            )
            pole_world = _point_from_frame(source_elbow_body, target_torso)
            solution = solve_two_bone_positions(
                target_world[f"{side}bicep_g"].position,
                target_world[f"{side}forearm_g"].position,
                target_world[f"{side}hand_g"].position,
                goal_world,
                pole_world,
            )
            expected[side] = np.asarray(_point_in_frame(
                solution.target_position, target_torso), dtype=np.float64)
        error = float(np.linalg.norm(
            (actual["l"] - actual["r"])
            - (expected["l"] - expected["r"])
        ))
        if error > max_error:
            max_error = error
            max_time = float(time_value)
    return {
        "samples": len(sample_times),
        "max_grip_vector_error": max_error,
        "max_time": max_time,
        "max_fraction": max_time / length if length > 1.0e-9 else 0.0,
    }


def audit_arm_torso_clearance(
        anim, rigged, *, start_fraction=0.0, end_fraction=1.0,
        sample_rate=30.0):
    """Count hand/robe safety-volume violations over a selected clip window."""
    import math as _math
    from src.core.animation.animation_engine import evaluate_aurora_animation_pose

    length = max(0.0, float(getattr(anim, "length", 0.0) or 0.0))
    start_time = length * max(0.0, min(1.0, float(start_fraction)))
    end_time = length * max(0.0, min(1.0, float(end_fraction)))
    if end_time < start_time:
        start_time, end_time = end_time, start_time
    sample_times = [
        index / float(sample_rate)
        for index in range(
            int(_math.floor(start_time * float(sample_rate))),
            int(_math.ceil(end_time * float(sample_rate))) + 1,
        )
        if start_time <= index / float(sample_rate) <= end_time
    ]
    sample_times = _clean_animation_times(
        sample_times + [start_time, end_time], length)
    torso_violations = 0
    for time_value in sample_times:
        pose = evaluate_aurora_animation_pose(rigged, anim, time_value)
        world = _pose_world_by_name(pose)
        torso = world["torsoupr_g"]
        for side in ("r", "l"):
            hx, hy, _hz = _point_in_frame(world[f"{side}hand_g"].position, torso)
            radius = _math.hypot(hx, hy + 0.05)
            torso_violations += int(
                hy < -0.33 or (hy < 0.17 and radius < 0.39))
    return {"samples": len(sample_times), "torso_violations": torso_violations}


def _segments_distance(first_start, first_end, second_start, second_end):
    """Exact minimum distance between two closed 3D segments."""
    import numpy as np

    epsilon = 1.0e-12
    u = first_end - first_start
    v = second_end - second_start
    w = first_start - second_start
    a = float(u @ u)
    b = float(u @ v)
    c = float(v @ v)
    d = float(u @ w)
    e = float(v @ w)
    if a <= epsilon and c <= epsilon:
        return float(np.linalg.norm(first_start - second_start))
    if a <= epsilon:
        factor = max(0.0, min(1.0, e / c))
        return float(np.linalg.norm(first_start - (second_start + factor * v)))
    if c <= epsilon:
        factor = max(0.0, min(1.0, -d / a))
        return float(np.linalg.norm((first_start + factor * u) - second_start))
    denominator = a * c - b * b
    s_denominator = denominator
    t_denominator = denominator
    if denominator < epsilon:
        s_numerator = 0.0
        s_denominator = 1.0
        t_numerator = e
        t_denominator = c
    else:
        s_numerator = b * e - c * d
        t_numerator = a * e - b * d
        if s_numerator < 0.0:
            s_numerator = 0.0
            t_numerator = e
            t_denominator = c
        elif s_numerator > s_denominator:
            s_numerator = s_denominator
            t_numerator = e + b
            t_denominator = c
    if t_numerator < 0.0:
        t_numerator = 0.0
        if -d < 0.0:
            s_numerator = 0.0
        elif -d > a:
            s_numerator = s_denominator
        else:
            s_numerator = -d
            s_denominator = a
    elif t_numerator > t_denominator:
        t_numerator = t_denominator
        if -d + b < 0.0:
            s_numerator = 0.0
        elif -d + b > a:
            s_numerator = s_denominator
        else:
            s_numerator = -d + b
            s_denominator = a
    s_factor = (
        0.0 if abs(s_numerator) < epsilon
        else s_numerator / max(epsilon, s_denominator)
    )
    t_factor = (
        0.0 if abs(t_numerator) < epsilon
        else t_numerator / max(epsilon, t_denominator)
    )
    delta = w + s_factor * u - t_factor * v
    return float(np.linalg.norm(delta))


def _segment_triangle_distance(start, tip, a, b, c):
    """Exact minimum distance between a closed segment and one triangle."""
    import numpy as np
    from src.math.containment_fit import _point_triangle_distance

    direction = tip - start
    edge1 = b - a
    edge2 = c - a
    cross = np.cross(direction, edge2)
    determinant = float(edge1 @ cross)
    if abs(determinant) > 1.0e-12:
        inverse = 1.0 / determinant
        offset = start - a
        u = float(offset @ cross) * inverse
        q = np.cross(offset, edge1)
        v = float(direction @ q) * inverse
        time_value = float(edge2 @ q) * inverse
        if (-1.0e-9 <= u <= 1.0 + 1.0e-9
                and -1.0e-9 <= v
                and u + v <= 1.0 + 1.0e-9
                and -1.0e-9 <= time_value <= 1.0 + 1.0e-9):
            return 0.0
    return min(
        _point_triangle_distance(start, a, b, c),
        _point_triangle_distance(tip, a, b, c),
        _segments_distance(start, tip, a, b),
        _segments_distance(start, tip, b, c),
        _segments_distance(start, tip, c, a),
    )


def _point_segments_distances(point, starts, ends):
    """Vectorized point-to-segment distances for an ``(N, 3)`` edge set."""
    import numpy as np

    point = np.asarray(point, dtype=np.float64)
    starts = np.asarray(starts, dtype=np.float64)
    ends = np.asarray(ends, dtype=np.float64)
    directions = ends - starts
    denominator = np.einsum("ij,ij->i", directions, directions)
    factors = np.divide(
        np.einsum("ij,ij->i", point - starts, directions),
        denominator,
        out=np.zeros_like(denominator),
        where=denominator > 1.0e-12,
    )
    factors = np.clip(factors, 0.0, 1.0)
    closest = starts + directions * factors[:, None]
    return np.linalg.norm(closest - point, axis=1)


def _point_triangles_distances(point, triangles):
    """Vectorized equivalent of ``_point_triangle_distance``."""
    import numpy as np

    point = np.asarray(point, dtype=np.float64)
    triangles = np.asarray(triangles, dtype=np.float64)
    a = triangles[:, 0]
    b = triangles[:, 1]
    c = triangles[:, 2]
    ab = b - a
    ac = c - a
    normals = np.cross(ab, ac)
    normal_lengths = np.linalg.norm(normals, axis=1)
    safe_lengths = np.where(normal_lengths > 1.0e-12, normal_lengths, 1.0)
    unit_normals = normals / safe_lengths[:, None]
    plane_distance = np.einsum("ij,ij->i", point - a, unit_normals)
    projected = point - plane_distance[:, None] * unit_normals
    projected_delta = projected - a
    d00 = np.einsum("ij,ij->i", ab, ab)
    d01 = np.einsum("ij,ij->i", ab, ac)
    d11 = np.einsum("ij,ij->i", ac, ac)
    d20 = np.einsum("ij,ij->i", projected_delta, ab)
    d21 = np.einsum("ij,ij->i", projected_delta, ac)
    denominator = d00 * d11 - d01 * d01
    bary_v = np.divide(
        d11 * d20 - d01 * d21,
        denominator,
        out=np.zeros_like(denominator),
        where=np.abs(denominator) > 1.0e-12,
    )
    bary_w = np.divide(
        d00 * d21 - d01 * d20,
        denominator,
        out=np.zeros_like(denominator),
        where=np.abs(denominator) > 1.0e-12,
    )
    bary_u = 1.0 - bary_v - bary_w
    inside = (
        (normal_lengths > 1.0e-12)
        & (np.abs(denominator) > 1.0e-12)
        & (bary_u >= 0.0)
        & (bary_v >= 0.0)
        & (bary_w >= 0.0)
    )
    edge_distance = np.minimum.reduce((
        _point_segments_distances(point, a, b),
        _point_segments_distances(point, b, c),
        _point_segments_distances(point, c, a),
    ))
    vertex_distance = np.minimum.reduce((
        np.linalg.norm(point - a, axis=1),
        np.linalg.norm(point - b, axis=1),
        np.linalg.norm(point - c, axis=1),
    ))
    return np.where(
        inside,
        np.abs(plane_distance),
        np.where(normal_lengths <= 1.0e-12, vertex_distance, edge_distance),
    )


def _segment_edges_distances(start, tip, edge_starts, edge_ends):
    """Exact distances from one segment to an ``(N, 2, 3)`` edge set."""
    import numpy as np

    start = np.asarray(start, dtype=np.float64)
    tip = np.asarray(tip, dtype=np.float64)
    edge_starts = np.asarray(edge_starts, dtype=np.float64)
    edge_ends = np.asarray(edge_ends, dtype=np.float64)
    direction = tip - start
    direction_sq = float(direction @ direction)
    edge_direction = edge_ends - edge_starts
    edge_sq = np.einsum("ij,ij->i", edge_direction, edge_direction)

    candidates = [
        _point_segments_distances(start, edge_starts, edge_ends),
        _point_segments_distances(tip, edge_starts, edge_ends),
    ]
    for points in (edge_starts, edge_ends):
        if direction_sq <= 1.0e-12:
            candidates.append(np.linalg.norm(points - start, axis=1))
        else:
            factors = np.clip(((points - start) @ direction) / direction_sq, 0.0, 1.0)
            candidates.append(np.linalg.norm(
                start + factors[:, None] * direction - points, axis=1))

    if direction_sq > 1.0e-12:
        offset = start - edge_starts
        cross_dot = edge_direction @ direction
        start_dot = offset @ direction
        edge_dot = np.einsum("ij,ij->i", edge_direction, offset)
        determinant = direction_sq * edge_sq - cross_dot * cross_dot
        start_factor = np.divide(
            cross_dot * edge_dot - edge_sq * start_dot,
            determinant,
            out=np.zeros_like(determinant),
            where=np.abs(determinant) > 1.0e-12,
        )
        edge_factor = np.divide(
            direction_sq * edge_dot - cross_dot * start_dot,
            determinant,
            out=np.zeros_like(determinant),
            where=np.abs(determinant) > 1.0e-12,
        )
        interior = (
            (np.abs(determinant) > 1.0e-12)
            & (start_factor >= 0.0)
            & (start_factor <= 1.0)
            & (edge_factor >= 0.0)
            & (edge_factor <= 1.0)
        )
        delta = (
            offset
            + start_factor[:, None] * direction
            - edge_factor[:, None] * edge_direction
        )
        candidates.append(np.where(
            interior, np.linalg.norm(delta, axis=1), np.inf))
    return np.minimum.reduce(candidates)


def _segment_triangles_distance(start, tip, triangles):
    """Exact vectorized minimum from a closed segment to triangle soup."""
    import numpy as np

    start = np.asarray(start, dtype=np.float64)
    tip = np.asarray(tip, dtype=np.float64)
    triangles = np.asarray(triangles, dtype=np.float64)
    if triangles.ndim != 3 or triangles.shape[1:] != (3, 3) or not len(triangles):
        raise AssertionError(f"invalid head triangle soup {triangles.shape}")
    a = triangles[:, 0]
    b = triangles[:, 1]
    c = triangles[:, 2]
    direction = tip - start

    # Moller-Trumbore intersection, vectorized over every head triangle.
    edge1 = b - a
    edge2 = c - a
    cross = np.cross(direction, edge2)
    determinant = np.einsum("ij,ij->i", edge1, cross)
    nonparallel = np.abs(determinant) > 1.0e-12
    inverse = np.divide(
        1.0,
        determinant,
        out=np.zeros_like(determinant),
        where=nonparallel,
    )
    offset = start - a
    bary_u = np.einsum("ij,ij->i", offset, cross) * inverse
    q = np.cross(offset, edge1)
    bary_v = (q @ direction) * inverse
    segment_factor = np.einsum("ij,ij->i", edge2, q) * inverse
    intersects = (
        nonparallel
        & (bary_u >= -1.0e-9)
        & (bary_u <= 1.0 + 1.0e-9)
        & (bary_v >= -1.0e-9)
        & (bary_u + bary_v <= 1.0 + 1.0e-9)
        & (segment_factor >= -1.0e-9)
        & (segment_factor <= 1.0 + 1.0e-9)
    )
    if bool(np.any(intersects)):
        return 0.0
    distances = np.concatenate((
        _point_triangles_distances(start, triangles),
        _point_triangles_distances(tip, triangles),
        _segment_edges_distances(start, tip, a, b),
        _segment_edges_distances(start, tip, b, c),
        _segment_edges_distances(start, tip, c, a),
    ))
    return float(np.min(distances))


def _head_only_skin_part(rigged, animation_name):
    """Return the one skin partition wholly owned by the Ithorian head rig."""
    allowed_head_bones = {
        "neckbase_g", "neck_g", "neckupr_g", "neckupr02_g",
        "neckupr03_g", "head_g", "lclothflap_g", "rclothflap_g",
    }
    candidates = []
    for node in rigged.all_nodes():
        bone_names = {
            str(name or "").strip().lower()
            for name in (getattr(node, "bone_map", None) or [])
            if str(name or "").strip()
        }
        if (getattr(node, "is_skin", False)
                and getattr(node, "vertices", None)
                and "head_g" in bone_names
                and bone_names <= allowed_head_bones):
            candidates.append(node)
    if len(candidates) != 1:
        raise AssertionError(
            f"{animation_name}: expected one head-only skin, found "
            f"{[str(node.name) for node in candidates]}")
    return candidates[0]


def _head_surface_triangles_in_torso_space(anim, rigged):
    """Build and verify the static upright head collider in torso space."""
    import numpy as np
    from src.core.animation.animation_engine import evaluate_aurora_animation_pose

    head_part = _head_only_skin_part(rigged, str(anim.name))
    length = max(0.0, float(getattr(anim, "length", 0.0) or 0.0))

    def triangles_at(time_value):
        posed_parts, _world_positions = deformed_parts(
            rigged, [head_part], str(anim.name), float(time_value))
        vertices = np.asarray(posed_parts[0][0], dtype=np.float64)
        faces = np.asarray([
            tuple(int(index) for index in face[:3])
            for face in posed_parts[0][1]
            if len(face) >= 3
        ], dtype=np.int64)
        if not len(faces):
            raise AssertionError(f"{anim.name}: head skin has no triangle faces")
        pose = evaluate_aurora_animation_pose(rigged, anim, float(time_value))
        torso = _pose_world_by_name(pose)["torsoupr_g"]
        torso_vertices = np.asarray([
            _point_in_frame(tuple(vertex), torso) for vertex in vertices
        ], dtype=np.float64)
        return torso_vertices[faces]

    triangles = triangles_at(0.0)
    if length > 1.0e-9:
        end_triangles = triangles_at(length)
        drift = float(np.max(np.abs(end_triangles - triangles)))
        if drift > 1.0e-5:
            raise AssertionError(
                f"{anim.name}: upright head surface is not torso-static "
                f"({drift:.6f}m endpoint drift)")
    return triangles


def audit_saber_head_surface_clearance(
        anim, rigged, *, start_fraction, end_fraction,
        extra_fractions=(), sample_rate=30.0):
    """Measure the attached red-saber centerline against posed head skin."""
    import math as _math
    import numpy as np
    from src.core.animation.animation_engine import evaluate_aurora_animation_pose

    head_part = _head_only_skin_part(rigged, str(anim.name))
    head_triangles_body = _head_surface_triangles_in_torso_space(anim, rigged)

    length = max(0.0, float(getattr(anim, "length", 0.0) or 0.0))
    start_time = length * max(0.0, min(1.0, float(start_fraction)))
    end_time = length * max(0.0, min(1.0, float(end_fraction)))
    if end_time < start_time:
        start_time, end_time = end_time, start_time
    sample_times = [
        index / float(sample_rate)
        for index in range(
            int(_math.floor(start_time * float(sample_rate))),
            int(_math.ceil(end_time * float(sample_rate))) + 1,
        )
        if start_time <= index / float(sample_rate) <= end_time
    ]
    sample_times.extend(
        length * max(0.0, min(1.0, float(fraction)))
        for fraction in extra_fractions
    )
    sample_times = _clean_animation_times(
        sample_times + [start_time, end_time], length)

    minimum = float("inf")
    minimum_time = 0.0
    for time_value in sample_times:
        pose = evaluate_aurora_animation_pose(rigged, anim, time_value)
        world = _pose_world_by_name(pose)
        socket = world.get("rhand")
        if socket is None:
            raise AssertionError(f"{anim.name}: animated rhand socket missing")
        torso = world["torsoupr_g"]
        socket_q = tuple(float(c) for c in socket.rotation[:4])
        start_world = np.asarray(socket.position, dtype=np.float64) + np.asarray(
            _quat_rotate_vec_xyzw(
                socket_q, RIGHT_SABER_CENTERLINE_LOCAL[0]),
            dtype=np.float64,
        )
        tip_world = np.asarray(socket.position, dtype=np.float64) + np.asarray(
            _quat_rotate_vec_xyzw(
                socket_q, RIGHT_SABER_CENTERLINE_LOCAL[1]),
            dtype=np.float64,
        )
        start = np.asarray(
            _point_in_frame(tuple(start_world), torso), dtype=np.float64)
        tip = np.asarray(
            _point_in_frame(tuple(tip_world), torso), dtype=np.float64)
        axis = tip - start
        denominator = float(axis @ axis)
        if denominator <= 1.0e-12:
            raise AssertionError(f"{anim.name}: degenerate saber centerline")
        clearance = _segment_triangles_distance(
            start, tip, head_triangles_body)
        if not np.isfinite(clearance):
            raise AssertionError(f"{anim.name}: head skin has no triangle faces")
        if clearance < minimum:
            minimum = clearance
            minimum_time = float(time_value)
    return {
        "samples": len(sample_times),
        "min_clearance": minimum,
        "min_time": minimum_time,
        "min_fraction": minimum_time / length if length > 1.0e-9 else 0.0,
        "head_part": str(head_part.name),
    }


def audit_saber_core_body_surface_clearance(
        anim, rigged, *, start_fraction=0.0, end_fraction=1.0,
        extra_fractions=(), sample_rate=120.0):
    """Measure the attached saber against the posed upper torso/neck skin."""
    import math as _math
    import numpy as np
    from src.core.animation.animation_engine import evaluate_aurora_animation_pose

    length = max(0.0, float(getattr(anim, "length", 0.0) or 0.0))
    start_time = length * max(0.0, min(1.0, float(start_fraction)))
    end_time = length * max(0.0, min(1.0, float(end_fraction)))
    if end_time < start_time:
        start_time, end_time = end_time, start_time
    sample_times = [
        index / float(sample_rate)
        for index in range(
            int(_math.floor(start_time * float(sample_rate))),
            int(_math.ceil(end_time * float(sample_rate))) + 1,
        )
        if start_time <= index / float(sample_rate) <= end_time
    ]
    sample_times.extend(
        length * max(0.0, min(1.0, float(fraction)))
        for fraction in extra_fractions
    )
    sample_times = _clean_animation_times(
        sample_times + [start_time, end_time], length)
    triangles_by_time = _set4_core_body_surface_triangles_at_times(
        anim, rigged, sample_times)
    _parts, face_rows = _set4_core_body_surface_parts(rigged)

    minimum = float("inf")
    minimum_time = 0.0
    for sample_index, time_value in enumerate(sample_times):
        pose = evaluate_aurora_animation_pose(rigged, anim, time_value)
        world = _pose_world_by_name(pose)
        socket = world.get("rhand")
        if socket is None:
            raise AssertionError(f"{anim.name}: animated rhand socket missing")
        torso = world["torsoupr_g"]
        socket_q = tuple(float(component) for component in socket.rotation[:4])
        start_world = np.asarray(socket.position, dtype=np.float64) + np.asarray(
            _quat_rotate_vec_xyzw(
                socket_q, RIGHT_SABER_CENTERLINE_LOCAL[0]),
            dtype=np.float64,
        )
        tip_world = np.asarray(socket.position, dtype=np.float64) + np.asarray(
            _quat_rotate_vec_xyzw(
                socket_q, RIGHT_SABER_CENTERLINE_LOCAL[1]),
            dtype=np.float64,
        )
        start = np.asarray(
            _point_in_frame(tuple(start_world), torso), dtype=np.float64)
        tip = np.asarray(
            _point_in_frame(tuple(tip_world), torso), dtype=np.float64)
        clearance = _segment_triangles_distance(
            start, tip, triangles_by_time[sample_index])
        if not np.isfinite(clearance):
            raise AssertionError(
                f"{anim.name}: core-body skin has no triangle faces")
        if clearance < minimum:
            minimum = float(clearance)
            minimum_time = float(time_value)
    return {
        "samples": len(sample_times),
        "min_clearance": minimum,
        "min_time": minimum_time,
        "min_fraction": minimum_time / length if length > 1.0e-9 else 0.0,
        "surface_faces": sum(len(rows) for rows in face_rows),
    }


# T2567 arm-pose clamp (body frame, relative to rootdummy):
# the Ithorian's arms are far longer than the humanoid donor's, so preserved
# humanoid shoulder orientations sweep the hands deep BEHIND the body and
# drive the attached saber through the robe.  Constraints derived from the
# Ithorian rest pose (hands at body-y ~= -0.22, radial ~0.52):
ARM_CLAMP_BACK_Y = -0.12          # hands never further back than this (user: shift forward — DJ holds saber in front)
ARM_CLAMP_TORSO_RADIUS = 0.45     # keep hands outside the torso capsule...
ARM_CLAMP_FRONT_Y = 0.20          # ...unless clearly in front of the body
ARM_CLAMP_MAX_ANGLE = 2.1         # rad; allow deep wind-up corrections (~120deg)


def clamp_arm_pose_keys(anim, rigged):
    """Post-retarget cleanup: keep hands frontal + outside the torso (T2567).

    For each side, at every bicep orientation-key time, FK the CONVERTED clip
    on the Ithorian skeleton, express the hand in the rootdummy body frame,
    and if it violates the back-plane or torso-capsule constraints rotate the
    bicep (world-frame, about the shoulder) by the minimal arc that moves the
    hand to the constraint boundary.  Children keep their locals, so the
    whole arm swings forward rigidly — pose character is preserved.
    """
    from src.core.animation.animation_engine import evaluate_aurora_animation_pose

    anim_by_name = {
        str(n.name or "").strip().lower(): n for n in (anim.nodes or [])
    }
    clamped = 0
    length = float(getattr(anim, "length", 0.0) or 0.0)
    rig_nodes = {
        str(n.name or "").strip().lower(): n for n in rigged.all_nodes()
    }
    for side in ("r", "l"):
        bicep = anim_by_name.get(f"{side}bicep_g")
        if bicep is None:
            # T2567c: clips whose source never keys the bicep still swing the
            # resting arm behind the body via TORSO rotation (user's c2a6
            # screenshot: left hand parked behind the back).  Create the
            # track so the clamp has something to correct.
            rig_bicep = rig_nodes.get(f"{side}bicep_g")
            if rig_bicep is None:
                continue
            parent_anim = None
            walker = rig_bicep.parent
            while walker is not None and parent_anim is None:
                parent_anim = anim_by_name.get(
                    str(walker.name or "").strip().lower())
                walker = walker.parent
            if parent_anim is None:
                continue
            bicep = md.ModelNode(name=str(rig_bicep.name))
            rest_q = [float(c) for c in (rig_bicep.rotation or (0, 0, 0, 1))[:4]]
            bicep.controllers = [{
                # full writer schema — a bare dict exports corrupted keys
                "type": 20,
                "name": "orientation",
                "columns": 4,
                "binary_column_count": 4,
                "binary_unknown0": 28,
                "binary_unknown1": [0, 0, 0],
                "times": [0.0, max(0.033, length)],
                "values": [list(rest_q), list(rest_q)],
            }]
            bicep.parent = parent_anim
            parent_anim.children = list(parent_anim.children or []) + [bicep]
            anim.nodes = list(anim.nodes) + [bicep]
            anim_by_name[f"{side}bicep_g"] = bicep
        ctrl = next((c for c in (bicep.controllers or []) if c.get("type") == 20), None)
        if ctrl is None or not ctrl.get("times"):
            continue
        # T2567b: enforce DENSELY, not just at bicep keys — the forearm's own
        # keys swing the hand between bicep keys (user screenshot: c2a2 at
        # t=1.371 buries the hand in the torso mid-interval).  Sample every
        # 1/30s plus the original keys; violating samples become NEW keys.
        orig_times = [float(t) for t in ctrl["times"]]
        orig_values = [list(v) for v in ctrl["values"]]
        dense = sorted(set(
            orig_times
            + [round(i / 30.0, 4) for i in range(int(length * 30.0) + 1)]
        ))
        times = dense
        values = []
        # seed values by sampling current local rotation at each dense time
        import bisect as _bisect
        def sample_local(t):
            if not orig_times:
                return None
            if t <= orig_times[0]:
                return list(orig_values[0])
            if t >= orig_times[-1]:
                return list(orig_values[-1])
            j = _bisect.bisect_right(orig_times, t) - 1
            t0, t1 = orig_times[j], orig_times[j + 1]
            f = (t - t0) / max(1e-9, t1 - t0)
            q0, q1 = orig_values[j], orig_values[j + 1]
            d = sum(a * b for a, b in zip(q0, q1))
            q1s = [c if d >= 0 else -c for c in q1]
            return list(_quat_norm_xyzw(tuple(
                (1 - f) * a + f * b for a, b in zip(q0, q1s))))
        values = [sample_local(t) for t in times]
        for ki, t in enumerate(times):
            pose = evaluate_aurora_animation_pose(rigged, anim, t)
            world = {
                str(k).strip().lower(): v
                for k, v in pose.world_transforms_by_node.items()
            }
            hand = world.get(f"{side}hand_g")
            shoulder = world.get(f"{side}bicep_g")
            rd = world.get("rootdummy")
            parent = None
            for node in rigged.all_nodes():
                if str(node.name or "").strip().lower() == f"{side}bicep_g":
                    parent = node.parent
                    break
            if hand is None or shoulder is None or rd is None or parent is None:
                continue
            rd_rot = tuple(float(c) for c in rd.rotation[:4])
            rd_inv = _quat_inv_xyzw(rd_rot)
            h = _quat_rotate_vec_xyzw(rd_inv, tuple(
                float(a) - float(b) for a, b in zip(hand.position, rd.position)))
            hx, hy, hz = h
            nx, ny = hx, hy
            import math as _math
            violated = False
            if hy < ARM_CLAMP_BACK_Y:
                # reflect about the back plane (capped) — the user wants the
                # hand IN FRONT at comparable distance, not parked on the
                # boundary
                ny = min(0.10, ARM_CLAMP_BACK_Y + (ARM_CLAMP_BACK_Y - hy))
                violated = True
            # T2567f head clearance: the Ithorian's head juts forward, so a
            # hand raised to head height must sit forward of the face or the
            # saber skewers the skull (user's c2a1 end-pose screenshot).
            if hz > 0.30 and ny < 0.14:
                ny = 0.14
                violated = True
            rho = _math.hypot(nx, ny + 0.05)
            if ny < ARM_CLAMP_FRONT_Y and rho < ARM_CLAMP_TORSO_RADIUS:
                if rho < 1e-6:
                    nx = ARM_CLAMP_TORSO_RADIUS if side == "r" else -ARM_CLAMP_TORSO_RADIUS
                    ny = max(ny, -0.05)
                else:
                    scale = ARM_CLAMP_TORSO_RADIUS / rho
                    nx = nx * scale
                    ny = (ny + 0.05) * scale - 0.05
                violated = True
            if not violated:
                continue
            target_body = (nx, ny, hz)
            target_world = tuple(
                float(rp) + d for rp, d in zip(
                    rd.position, _quat_rotate_vec_xyzw(rd_rot, target_body)))
            u = tuple(float(a) - float(b) for a, b in zip(hand.position, shoulder.position))
            v = tuple(float(a) - float(b) for a, b in zip(target_world, shoulder.position))
            rot = _quat_between_vecs(u, v)
            ang = 2.0 * _math.acos(max(-1.0, min(1.0, abs(rot[3]))))
            if ang > ARM_CLAMP_MAX_ANGLE:
                s = ARM_CLAMP_MAX_ANGLE / ang
                half = 0.5 * ang * s
                axis_n = _math.sqrt(max(1e-12, rot[0]**2 + rot[1]**2 + rot[2]**2))
                rot = _quat_norm_xyzw((
                    rot[0] / axis_n * _math.sin(half),
                    rot[1] / axis_n * _math.sin(half),
                    rot[2] / axis_n * _math.sin(half),
                    _math.cos(half)))
            bicep_world = tuple(float(c) for c in shoulder.rotation[:4])
            new_world = _quat_norm_xyzw(_quat_mul_xyzw(rot, bicep_world))
            parent_world = world.get(str(parent.name or "").strip().lower())
            if parent_world is None:
                continue
            pw = tuple(float(c) for c in parent_world.rotation[:4])
            new_local = _quat_norm_xyzw(
                _quat_mul_xyzw(_quat_inv_xyzw(pw), new_world))
            values[ki] = list(new_local)
            clamped += 1
        ctrl["times"] = list(times)
        ctrl["values"] = values
    return clamped


def bake_one_clip(rigged, source_model, src_name, target_name, tree_names,
                  root_name):
    """Retarget ONE source clip onto the rigged creature as a local animation.

    Deep-copies the source Animation, prunes anim nodes to bones present on
    the target skeleton, renames nodes to the EXACT target casing, renames the
    anim root (T2538 contract), and world-space retargets every orientation
    track (T2564). The binary writer verifies the carried parent edges against
    the target and rebuilds any donor-shaped tree on the target ancestor
    closure before serialization. Position keys are parent-local deltas at
    anim_scale 1.0 and pass through. Events ride along. Returns a report line
    or None if the clip keeps no usable nodes.
    """
    import copy as _copy

    src = next(
        (a for a in source_model.animations
         if str(a.name or "").lower() == src_name.lower()),
        None,
    )
    assert src is not None, f"source clip {src_name} missing from donor"
    anim = _copy.deepcopy(src)
    anim.name = target_name
    anim.anim_root = root_name
    excluded_events = ANIMATION_EVENT_EXCLUDE_BY_TARGET.get(
        str(target_name or "").strip().lower(), set())
    if excluded_events:
        anim.events = [
            event for event in (anim.events or [])
            if str(getattr(event, "name", "") or "").strip().lower()
            not in excluded_events
        ]
    nodes = list(anim.nodes or [])
    if not nodes:
        return None
    keep_ids = set()
    for idx, node in enumerate(nodes):
        name = str(getattr(node, "name", "") or "").strip().lower()
        if idx == 0 or name in tree_names:
            keep_ids.add(id(node))
    kept = []
    for node in nodes:
        if id(node) not in keep_ids:
            continue
        parent = getattr(node, "parent", None)
        while parent is not None and id(parent) not in keep_ids:
            parent = getattr(parent, "parent", None)
        node.parent = parent
        node.children = []
        exact = tree_names.get(str(getattr(node, "name", "") or "").strip().lower())
        if exact:
            node.name = exact
        kept.append(node)
    if len(kept) <= 1:
        return None
    for node in kept:
        if node.parent is not None:
            node.parent.children.append(node)
    kept[0].name = root_name
    anim.nodes = kept
    converted = retarget_clip_orientations(anim, source_model, src_name, rigged)
    clamped = 0   # T2567e: clamping moved post-export — bake-frame corrections
                  # never land in the shipped file (export relocation)
    rigged.animations.append(anim)
    return (
        f"{target_name}<-{src_name} (nodes {len(nodes)}->{len(kept)}, "
        f"len {anim.length:.2f}s, events {len(anim.events or [])}, "
        f"retargeted tracks {converted}, arm keys clamped {clamped})"
    )


def load_animation_chain(mgr, body_resref):
    """Resolve the body's supermodel chain; return [(name, model), ...]."""
    chain = []
    name = body_resref
    seen = set()
    while name and name.upper() != "NULL" and name.lower() not in seen:
        seen.add(name.lower())
        model = mgr.load_model(name, "K1", prefer_base_archive=True)
        assert model is not None, f"chain model {name} failed to load"
        chain.append((name, model))
        name = str(model.supermodel or "NULL")
    return chain


def load_malak_combat_sources(mgr):
    """Load Malak's self-contained model and validate every requested source."""
    model = mgr.load_model(MALAK_COMBAT_DONOR, "K1", prefer_base_archive=True)
    assert model is not None, f"combat donor {MALAK_COMBAT_DONOR} failed to load"
    by_name = {
        str(animation.name or "").strip().lower(): animation
        for animation in (model.animations or [])
        if str(animation.name or "").strip()
    }
    requested = {
        *(str(name).lower() for name in MALAK_COMBAT_SLOT_SOURCES.values()),
        *(str(name).lower() for name in COMBAT_ALIAS_SOURCES.values()),
    }
    missing = sorted(requested - set(by_name))
    assert not missing, (MALAK_COMBAT_DONOR, "missing animations", missing)
    return model, by_name


def effective_animation_source_map(mgr):
    """Return target -> source, with Malak winning combat-slot collisions."""
    effective = {}
    for _owner_name, model in load_animation_chain(mgr, ANIMATION_DONOR_BODY):
        for animation in model.animations:
            key = str(animation.name or "").strip().lower()
            if key and key not in effective:
                effective[key] = (model, key)
    result = dict(effective)
    for target_name, source_name in ANIMATION_SOURCE_OVERRIDES.items():
        source_model, canonical_name = effective[source_name.lower()]
        result[target_name.lower()] = (source_model, canonical_name)
    for alias, source_name in COMBAT_ALIAS_SOURCES.items():
        source_model, canonical_name = effective[source_name.lower()]
        result[alias.lower()] = (source_model, canonical_name)
    malak_model, _malak_by_name = load_malak_combat_sources(mgr)
    for target_name, source_name in MALAK_COMBAT_SLOT_SOURCES.items():
        result[target_name.lower()] = (malak_model, source_name.lower())
    for alias, source_name in COMBAT_ALIAS_SOURCES.items():
        result[alias.lower()] = (malak_model, source_name.lower())
    return result


def bake_full_inventory(rigged, mgr):
    """Bake the broad humanoid inventory with Malak combat precedence.

    Chain priority = nearest model wins (same rule the engine uses).  The
    16 native Ithorian clips win all name collisions. Malak then wins every
    declared combat-slot collision. Each clip retargets against the rig that
    owns its source motion (male/female rest frames differ).
    """
    tree_names = {
        str(n.name or "").strip().lower(): str(n.name or "").strip()
        for n in rigged.all_nodes()
        if str(n.name or "").strip()
    }
    root_name = str(rigged.root_node.name)
    native = {str(a.name or "").lower() for a in rigged.animations}
    chain = load_animation_chain(mgr, ANIMATION_DONOR_BODY)
    effective = {}
    for owner_name, model in chain:
        for a in model.animations:
            key = str(a.name or "").lower()
            if key and key not in effective:
                effective[key] = (owner_name, model)
    assert len(ANIMATION_SOURCE_OVERRIDES) == 41, len(ANIMATION_SOURCE_OVERRIDES)
    missing_override_sources = sorted(
        source for source in ANIMATION_SOURCE_OVERRIDES.values()
        if source.lower() not in effective
    )
    assert not missing_override_sources, missing_override_sources
    malak_model, malak_by_name = load_malak_combat_sources(mgr)
    baked = 0
    skipped_native = 0
    skipped_empty = 0
    inventory_targets = set(effective) | set(MALAK_COMBAT_SLOT_SOURCES)
    for key in sorted(inventory_targets):
        if key in native:
            skipped_native += 1
            continue
        if key in MALAK_COMBAT_SLOT_SOURCES:
            source_name = MALAK_COMBAT_SLOT_SOURCES[key]
            owner_name, model = MALAK_COMBAT_DONOR, malak_model
            assert source_name.lower() in malak_by_name
        else:
            source_name = ANIMATION_SOURCE_OVERRIDES.get(key, key)
            owner_name, model = effective[source_name.lower()]
        line = bake_one_clip(
            rigged, model, source_name, key, tree_names, root_name)
        if line is None:
            skipped_empty += 1
            continue
        baked += 1
    alias_lines = []
    for alias, src_name in COMBAT_ALIAS_SOURCES.items():
        assert src_name.lower() in malak_by_name
        line = bake_one_clip(
            rigged, malak_model, src_name, alias, tree_names, root_name)
        assert line is not None, alias
        alias_lines.append(line)
        baked += 1
    print(f"inventory bake: {baked} clips baked "
          f"({skipped_native} native kept, {skipped_empty} empty skipped) "
          f"from chain {'->'.join(n for n, _ in chain)}")
    print(
        f"  Malak combat payload overrides: {len(MALAK_COMBAT_SLOT_SOURCES)}; "
        f"optional Set 4 inventory mappings kept: {len(ANIMATION_SOURCE_OVERRIDES)}")
    for line in alias_lines:
        print(f"  alias {line}")
    return baked


def strip_stray_origin_islands(node, *, max_verts=60, radius=0.3, max_z=0.25):
    """Remove tiny leftover DCC objects near the ground origin (T2566).

    The user's edited OBJ carries a small untextured cone at the robe hem
    (bind ~(0,-0.13,0)).  Its verts sit exactly between the feet, the donor
    transfer splits them LFoot/RFoot, and every stride tears it 1.375m —
    tripping the cross-shell gate.  Strip any island that small, that low,
    and that close to the centreline before rigging.
    """
    import numpy as np
    verts = list(getattr(node, "vertices", []) or [])
    faces = [tuple(int(i) for i in f[:3]) for f in (getattr(node, "faces", []) or [])]
    if not verts or not faces:
        return 0
    parent = list(range(len(verts)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b, c in faces:
        for u, v in ((a, b), (b, c)):
            ru, rv = find(u), find(v)
            if ru != rv:
                parent[ru] = rv
    from collections import defaultdict
    isl = defaultdict(list)
    for i in range(len(verts)):
        isl[find(i)].append(i)
    doomed = set()
    pts = np.asarray([[float(c) for c in v[:3]] for v in verts])
    for members in isl.values():
        if len(members) > max_verts:
            continue
        p = pts[members]
        if p[:, 2].max() < max_z and np.linalg.norm(p[:, :2], axis=1).max() < radius:
            doomed.update(members)
    if not doomed:
        return 0
    keep = [i for i in range(len(verts)) if i not in doomed]
    remap = {old: new for new, old in enumerate(keep)}
    node.vertices = [verts[i] for i in keep]
    for attr in ("uvs", "normals"):
        arr = list(getattr(node, attr, []) or [])
        if len(arr) == len(verts):
            setattr(node, attr, [arr[i] for i in keep])
    node.faces = [
        (remap[a], remap[b], remap[c])
        for a, b, c in faces
        if a in remap and b in remap and c in remap
    ]
    if getattr(node, "skin_data", None):
        node.skin_data = []
    return len(doomed)


def refine_hand_weights(rigged):
    """Per-finger bone-segment weighting for the hand region (T2566).

    Euclidean nearest-donor-vertex transfer confuses the tiny adjacent donor
    fingers (28-32% of finger verts mis-assigned; the user's screenshots show
    fingers stretching into spikes).  Vanilla KOTOR fingers are near-rigid
    tubes, so assign each hand-region vertex to its nearest FINGER BONE
    SEGMENT (hand->FngrB, FngrB->FngrT, FngrT->tip extension, thumb chain,
    palm->hand), with a short blend at shared knuckles.
    """
    import numpy as np
    from src.core.animation.animation_engine import (
        AuroraTransform, _compose_transform, _normalize_quat_xyzw,
    )

    world = {}

    def walk(n, w):
        w2 = _compose_transform(w, AuroraTransform(
            position=tuple(float(c) for c in n.position),
            rotation=_normalize_quat_xyzw(list(n.rotation))))
        world[str(n.name or "").lower()] = np.asarray(w2.position)
        for c in n.children or []:
            walk(c, w2)

    walk(rigged.root_node, None)

    def seg_dist(p, a, b):
        ab = b - a
        t = float(np.dot(p - a, ab) / max(1e-9, np.dot(ab, ab)))
        t = min(1.0, max(0.0, t))
        return float(np.linalg.norm(p - (a + t * ab)))

    total_reassigned = 0
    for payload in rigged.all_nodes():
        if not getattr(payload, "is_skin", False) or not getattr(payload, "vertices", None):
            continue
        bm = [str(b or "") for b in (payload.bone_map or [])]
        bml = [b.lower() for b in bm]
        slot_of = {b: i for i, b in enumerate(bml)}
        try:
            from core.geometry.model_data import BoneWeight, VertexSkinData  # type: ignore
        except ImportError:
            from src.core.geometry.model_data import BoneWeight, VertexSkinData  # type: ignore
        for side in ("r", "l"):
            hand = f"{side}hand_g"
            if hand not in slot_of or hand not in world:
                continue
            segments = []   # (bone_lower, a, b)
            hp = world[hand]
            for fam in ("a", "b", "c"):
                base = f"{side}{fam}fngrb_g"
                tip = f"{side}{fam}fngrt_g"
                if base in world and tip in world:
                    segments.append((base, hp, world[base]))
                    ext = world[tip] + (world[tip] - world[base]) * 0.9
                    segments.append((tip, world[base], ext))
            tb, tt = f"{side}thumbb_g", f"{side}thumbt_g"
            if tb in world and tt in world:
                segments.append((tb, hp, world[tb]))
                segments.append((tt, world[tb], world[tt] + (world[tt] - world[tb]) * 0.9))
            fore = f"{side}forearm_g"
            if fore in world:
                segments.append((hand, world[fore] + (hp - world[fore]) * 0.6, hp))
            segments = [(b, a, c) for b, a, c in segments if b in slot_of]
            if not segments:
                continue
            hand_family = {s for s in bml if s.startswith(side) and (
                "fngr" in s or "thumb" in s or s == hand)}
            for vi, row in enumerate(list(payload.skin_data or [])):
                dom = max((b for b in row.influences if b.weight > 1e-6),
                          key=lambda b: b.weight, default=None)
                if dom is None or dom.bone_index >= len(bml):
                    continue
                if bml[dom.bone_index] not in hand_family:
                    continue
                p = np.asarray([float(c) for c in payload.vertices[vi][:3]])
                scored = sorted(
                    ((seg_dist(p, a, b), bone) for bone, a, b in segments),
                    key=lambda t: t[0])
                d1, b1 = scored[0]
                influences = [BoneWeight(bone_index=slot_of[b1], weight=1.0)]
                if len(scored) > 1:
                    d2, b2 = scored[1]
                    if b2 != b1 and (d2 - d1) < 0.015:
                        w2 = 0.35
                        influences = [
                            BoneWeight(bone_index=slot_of[b1], weight=1.0 - w2),
                            BoneWeight(bone_index=slot_of[b2], weight=w2),
                        ]
                payload.skin_data[vi] = VertexSkinData(influences=influences)
                total_reassigned += 1
    return total_reassigned


def refine_centerline_leg_weights(rigged, *, band=0.06):
    """Symmetric L/R leg blend for robe-hem verts near the centreline (T2566).

    Hem vertices millimetres apart straddle x=0; nearest-donor transfer gives
    one 100% LFoot and its neighbour 100% RFoot, so every stride tears the
    hem 1.375m (the cross-shell gate's exact failure).  Blend leg-family
    weights across the centre band so the hem stretches like cloth instead:
    at x=0 the row becomes a 50/50 mirror mix, falling off linearly to the
    band edge.
    """
    try:
        from core.geometry.model_data import BoneWeight, VertexSkinData  # type: ignore
    except ImportError:
        from src.core.geometry.model_data import BoneWeight, VertexSkinData  # type: ignore

    leg_families = ("foot_g", "shin_g", "thigh_g", "toes_g")
    blended = 0
    for payload in rigged.all_nodes():
        if not getattr(payload, "is_skin", False) or not getattr(payload, "vertices", None):
            continue
        bm = [str(b or "").lower() for b in (payload.bone_map or [])]
        slot_of = {b: i for i, b in enumerate(bm)}

        def mirror(bone):
            if bone.startswith("l"):
                other = "r" + bone[1:]
            elif bone.startswith("r"):
                other = "l" + bone[1:]
            else:
                return None
            return slot_of.get(other)

        for vi, row in enumerate(list(payload.skin_data or [])):
            dom = max((b for b in row.influences if b.weight > 1e-6),
                      key=lambda b: b.weight, default=None)
            if dom is None or dom.bone_index >= len(bm):
                continue
            dbone = bm[dom.bone_index]
            if not any(dbone.endswith(f) for f in leg_families):
                continue
            x = float(payload.vertices[vi][0])
            if abs(x) >= band:
                continue
            mix = 0.5 * (1.0 - abs(x) / band)   # 0.5 at centre -> 0 at edge
            acc = {}
            for b in row.influences:
                if b.weight <= 1e-6 or b.bone_index >= len(bm):
                    continue
                acc[b.bone_index] = acc.get(b.bone_index, 0.0) + b.weight * (1.0 - mix)
                mi = mirror(bm[b.bone_index])
                if mi is not None:
                    acc[mi] = acc.get(mi, 0.0) + b.weight * mix
                else:
                    acc[b.bone_index] = acc.get(b.bone_index, 0.0) + b.weight * mix
            top = sorted(acc.items(), key=lambda t: -t[1])[:4]
            total = sum(w for _, w in top)
            payload.skin_data[vi] = VertexSkinData(influences=[
                BoneWeight(bone_index=i, weight=w / total) for i, w in top
            ])
            blended += 1
    return blended


def node_world_position(node):
    from src.core.animation.animation_engine import (
        AuroraTransform, _compose_transform, _normalize_quat_xyzw,
    )
    chain = []
    cur = node
    while cur is not None:
        chain.append(cur)
        cur = getattr(cur, "parent", None)
    world = None
    for x in reversed(chain):
        world = _compose_transform(
            world,
            AuroraTransform(
                position=tuple(float(v) for v in x.position),
                rotation=_normalize_quat_xyzw(list(x.rotation)),
            ),
        )
    return world.position


def skeleton_segments(model, positions_by_name):
    segs = []
    for n in model.all_nodes():
        p = getattr(n, "parent", None)
        if p is None:
            continue
        a = positions_by_name.get(str(n.name or ""))
        b = positions_by_name.get(str(p.name or ""))
        if a is not None and b is not None:
            segs.append((a, b))
    return segs


def render_overlay(png_path, mesh_arrays, seg_list, title):
    """Two-panel orthographic overlay: front (x/z) and side (y/z)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    fig, axes = plt.subplots(1, 2, figsize=(11, 7))
    for ax, (ix, lbl) in zip(axes, ((0, "front  (x/z)"), (1, "side  (y/z)"))):
        for verts, faces in mesh_arrays:
            v = np.asarray(verts)
            f = np.asarray(faces, dtype=int)
            if f.size:
                tri = v[f]
                # light mesh wireframe: every edge of every face
                for k in range(3):
                    seg = tri[:, [k, (k + 1) % 3], :]
                    ax.plot(
                        seg[:, :, ix].T, seg[:, :, 2].T,
                        color="0.75", linewidth=0.15, alpha=0.5, zorder=1,
                    )
        for a, b in seg_list:
            ax.plot(
                [a[ix], b[ix]], [a[2], b[2]],
                color="crimson", linewidth=1.6, zorder=3,
            )
            ax.plot(
                [a[ix]], [a[2]], marker="o", markersize=2.5,
                color="darkred", zorder=4,
            )
        ax.set_aspect("equal")
        ax.set_title(lbl, fontsize=9)
        ax.tick_params(labelsize=7)
    fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(png_path, dpi=110)
    plt.close(fig)


def deformed_parts(model, parts, clip_name, t):
    """Deform every split part through the production preview path."""
    import numpy as np
    from src.core.animation.animation_engine import evaluate_aurora_animation_pose
    from src.core.animation.gpu_skinning import MAX_BONES, MatrixPaletteUploader
    from src.core.characters.animation_deformation_validator import (
        _palette_pose_from_evaluated_pose,
        _skin_rows_to_arrays,
        _skin_vertices_with_palette,
    )

    anim = next(a for a in model.animations if str(a.name) == clip_name)
    pose_eval = evaluate_aurora_animation_pose(model, anim, float(t))
    pose = _palette_pose_from_evaluated_pose(pose_eval)
    out = []
    for mesh in parts:
        verts = np.asarray([tuple(float(c) for c in vx[:3]) for vx in mesh.vertices])
        slots = [str(b or "") for b in mesh.bone_map]
        weights, indices = _skin_rows_to_arrays(
            list(mesh.skin_data), verts.shape[0], len(slots))
        up = MatrixPaletteUploader(max_bones=max(int(MAX_BONES), len(slots)))
        up.build_inverse_bind_pose(model)
        deformed = _skin_vertices_with_palette(
            uploader=up, mesh=mesh, pose=pose, anim_base_pose=None,
            verts=verts, weights=weights, indices=indices)
        out.append((deformed, list(mesh.faces)))
    world = {
        str(name): tuple(entry.position)
        for name, entry in pose_eval.world_transforms_by_node.items()
    }
    return out, world


def build_variant(mgr, spec):
    import numpy as np
    from scipy.spatial import cKDTree
    from src.core.animation.gpu_skinning import MatrixPaletteUploader
    from src.math.gpu_math import _matrix_from_pos_quat_np

    resref = spec["resref"]
    print(f"\n=== {spec['display']} ({resref}) ===")
    _reset_set4_saber_plan_cache()

    def donor():
        return mgr.load_model(DONOR, "K1", prefer_base_archive=True)

    scene = md.CharacterScene(game_version="K1")
    scene.mode = md.CharacterMode.CREATURE
    load = wf.load_body(
        str(spec["obj"]), scene, game_version="K1",
        fit_reference_model=donor(), fit_reference_label=DONOR,
        expected_mode=md.CharacterMode.CREATURE, allow_mode_correction=True,
    )
    assert load.ok, (load.code, load.message)

    for n in list(load.model.all_nodes()):
        if getattr(n, "vertices", None) and getattr(n, "faces", None):
            b, a = weld_mesh_node(n)
            if b != a:
                print(f"weld: {getattr(n, 'name', '?')} {b} -> {a} verts")
            stripped = strip_stray_origin_islands(n)
            if stripped:
                print(f"stray-island strip: removed {stripped} verts near origin "
                      f"from {getattr(n, 'name', '?')} (T2566 white-cone class)")

    # T2563: graft the saber hand hooks into the donor TEMPLATE before the
    # rig, so the native-skeleton snapshot includes them and the export
    # preflight treats them as native (grafting after the rig trips the
    # "Non-native node remains in the final DAG" blocker).  Local transforms
    # from S_Male02; parent bones are shared with the Ithorian.
    template = donor()
    template_nodes = {
        str(n.name or "").strip().lower(): n for n in template.all_nodes()
    }
    for hook_name, parent_name, hook_pos, hook_rot in HAND_HOOKS:
        assert hook_name not in template_nodes, f"{hook_name} already present"
        parent_node = template_nodes[parent_name]
        hook = md.ModelNode(name=hook_name)
        hook.position = tuple(hook_pos)
        hook.rotation = tuple(hook_rot)
        # Retail weapon-bearing K1 models serialize static hook transforms as
        # one-frame controllers.  Node fields alone leave the equipped item in
        # the UTC but can prevent Odyssey from drawing it on custom creature
        # creatures.
        hook.controllers = [
            {
                "type": 8,
                "name": "position",
                "columns": 3,
                "times": [0.0],
                "values": [list(hook_pos)],
            },
            {
                "type": 20,
                "name": "orientation",
                "columns": 4,
                "times": [0.0],
                "values": [list(hook_rot)],
            },
        ]
        hook.parent = parent_node
        parent_node.children = list(parent_node.children or []) + [hook]
        print(f"hand hook grafted into template: {hook_name} under "
              f"{parent_node.name} pos={hook_pos}")

    rig = cb.apply_template_rig(load.model, template, game="K1")
    assert rig.get("ok"), rig.get("message")
    rigged = rig["model"]
    refined = refine_hand_weights(rigged)
    print(f"hand/finger segment reweight: {refined} verts (T2566)")
    hem = refine_centerline_leg_weights(rigged)
    print(f"centreline leg blend: {hem} verts (T2566)")
    zs = [v[2] for n in rigged.all_nodes() for v in (getattr(n, "vertices", []) or [])]
    print(f"rig: name={rigged.name} anim_scale={rigged.anim_scale} "
          f"supermodel={rigged.supermodel} anims={len(rigged.animations)} "
          f"height={max(zs) - min(zs):.3f}")

    scene.assign(
        md.PartSlot.HEADLESS_BODY, rigged,
        resref=resref, game_version="K1", source_path=str(spec["obj"]),
    )
    split = wf.split_imported_mesh_nodes(
        scene, respect_skinned="split_with_weight_remap",
        reference_model=donor(),
    )
    assert split.get("ok"), (split.get("code"), split.get("message"))
    print(f"split: {split.get('code')} nodes={split.get('split_nodes')}")

    # T2555 regression gate: the connectivity splitter must never orphan the
    # donor's neck/head bone chain again.
    present = {str(n.name or "").lower() for n in rigged.all_nodes()}
    missing_bones = sorted(NECK_CHAIN - present)
    assert not missing_bones, f"native bones orphaned by split: {missing_bones}"
    print(f"native-bone gate: neck/head chain intact ({len(NECK_CHAIN)} nodes)")

    parts = [
        n for n in rigged.all_nodes()
        if getattr(n, "is_skin", False) and getattr(n, "vertices", None)
        and getattr(n, "skin_data", None) and getattr(n, "bone_map", None)
    ]

    def assert_inverse_bind_contract(model, skin_nodes, *, node_indexed):
        nodes = list(model.all_nodes())
        by_name = {
            str(getattr(node, "name", "") or "").strip().lower(): node
            for node in nodes
            if str(getattr(node, "name", "") or "").strip()
        }
        max_error = 0.0
        checked = 0
        for skin_node in skin_nodes:
            skin_pos, skin_rot = wf._node_world_transform_or_local(skin_node)
            skin_world = _matrix_from_pos_quat_np(skin_pos, skin_rot)
            qbones = list(getattr(skin_node, "qbone_list", []) or [])
            tbones = list(getattr(skin_node, "tbone_list", []) or [])
            for slot, raw_name in enumerate(list(skin_node.bone_map or [])):
                name = str(raw_name or "").strip().lower()
                assert name in by_name, (skin_node.name, raw_name)
                bone = by_name[name]
                bind_index = nodes.index(bone) if node_indexed else slot
                assert 0 <= bind_index < len(qbones), (
                    skin_node.name, raw_name, bind_index, len(qbones))
                bone_pos, bone_rot = wf._node_world_transform_or_local(bone)
                bone_world = _matrix_from_pos_quat_np(bone_pos, bone_rot)
                inverse_bind = np.asarray(
                    MatrixPaletteUploader.qbone_inverse_bind_matrix_g5(
                        qbones[bind_index], tbones[bind_index]),
                    dtype=np.float64,
                )
                error = float(np.max(np.abs((bone_world @ inverse_bind) - skin_world)))
                max_error = max(max_error, error)
                checked += 1
        tolerance = 1.0e-4 if node_indexed else 1.0e-6
        assert max_error <= tolerance, (max_error, tolerance, checked)
        return checked, max_error

    bind_checked, bind_error = assert_inverse_bind_contract(
        rigged, parts, node_indexed=False)
    donor_ambient = wf._reference_skin_ambient(donor())
    assert donor_ambient is not None
    assert all(
        tuple(float(v) for v in part.ambient[:3])
        == tuple(float(v) for v in donor_ambient)
        for part in parts
    )
    print(f"inverse-bind gate: {bind_checked} rows, max_error={bind_error:.3g}; "
          f"ambient={donor_ambient}")

    points, owners = [], []
    for pi, part in enumerate(parts):
        world = wf._node_world_vertices_for_split(part, np)
        for vi in range(world.shape[0]):
            points.append(world[vi])
            owners.append((pi, vi))
    tree = cKDTree(np.asarray(points))
    pairs = tree.query_pairs(r=5e-4, output_type="ndarray")
    worst = 0.0
    bad = 0
    for a, b in pairs:
        pa, va = owners[int(a)]
        pb, vb = owners[int(b)]
        wa = effective_weights_by_name(
            parts[pa].skin_data[va], [str(x) for x in parts[pa].bone_map])
        wb = effective_weights_by_name(
            parts[pb].skin_data[vb], [str(x) for x in parts[pb].bone_map])
        d = weight_delta(wa, wb)
        worst = max(worst, d)
        if d > 1e-4:
            bad += 1
    print(f"seam check: {len(pairs)} coincident pairs, divergent={bad}, "
          f"worst_delta={worst:.6f}")
    assert bad == 0, "seam weight divergence detected"

    # ---- full N_DarkJediM inventory bake (T2565) ----------------------------
    baked_count = bake_full_inventory(rigged, mgr)
    assert baked_count >= 250, f"only {baked_count} clips baked"
    clip_names = {str(a.name or "").lower() for a in rigged.animations}
    for needed in ("g0a1", "g0a2", "creadyr", "c2a1", "castout1",
                   "cdamages", "tlknorm"):
        assert needed in clip_names, needed

    # ---- weight-regularization evidence (T2557) -----------------------------
    reg_reports = [
        dict(getattr(p, "_gr_skin_weight_regularization", {}) or {})
        for p in parts
        if getattr(p, "_gr_skin_weight_regularization", None)
    ]
    src_reg = None
    for n in rigged.all_nodes():
        rep = getattr(n, "_gr_skin_weight_regularization", None)
        if rep:
            src_reg = dict(rep)
            break
    if src_reg:
        print(f"weight regularization: islands={src_reg.get('islands')} "
              f"bridges={src_reg.get('bridge_links')} "
              f"anchors={src_reg.get('anchor_fraction')} "
              f"reweighted={src_reg.get('reweighted_vertices')} "
              f"dominant_reassigned={src_reg.get('dominant_bone_reassigned')}")

    # ---- deformation audit on a representative subset (T2565) --------------
    # 280+ clips make an exhaustive audit take an hour; gate the native 16,
    # the creature-contract clips, and a spread of humanoid sets (melee,
    # saber, flurry, blaster, casting, locomotion, dialogue).  The full
    # inventory still ships; this is the regression tripwire.
    GATE_CLIPS = {
        "cdamages", "cdie", "cwalk", "crun", "cgustandb", "ctaunt",
        "g0a1", "g0a2", "creadyr", "castout1", "castoutlp1",
        "c2a1", "c2d1", "c2p1", "g2a1", "f2a1", "g8a1", "b6a1",
        "walk", "run02", "pause1", "tlknorm", "horror", "choke",
    }
    all_animations = list(rigged.animations)
    rigged.animations = [
        a for a in all_animations
        if str(a.name or "").lower() in GATE_CLIPS
    ]
    report = audit_model(rigged, samples_per_animation=4)
    hard_fail = {}
    worst_stretch = {}
    for s in report["samples"]:
        a = s["animation"]
        worst_stretch[a] = max(worst_stretch.get(a, 1.0), s.get("max_edge_stretch", 1.0))
        hard = {"exploded_vertices", "missing_bone_transforms", "non_finite_vertices",
                "pose_evaluation_failed"} & set(s.get("failures", []))
        if hard:
            hard_fail.setdefault(a, set()).update(hard)
    print("animation audit (worst edge stretch per clip):")
    for a in sorted(worst_stretch, key=lambda k: -worst_stretch[k]):
        marks = ",".join(sorted(hard_fail.get(a, []))) or "ok"
        print(f"   {a:12s} {worst_stretch[a]:8.2f}  {marks}")
    assert not hard_fail, f"animation audit hard failures: {hard_fail}"
    (OUT / f"{resref}_animation_audit.json").write_text(
        json.dumps(report, indent=1), encoding="utf-8")

    # ---- cross-shell divergence gate (T2557) --------------------------------
    # Disconnected shells share no edges, so edge-stretch audits cannot see a
    # rigid plate tearing away from the body (the exact failure in the user's
    # 2026-07-10 video).  Measure it directly: vertex pairs closer than 3cm at
    # bind must not separate under animation.
    bind_pts = np.concatenate([
        np.asarray([tuple(float(c) for c in v[:3]) for v in p.vertices])
        for p in parts
    ])
    prox_tree = cKDTree(bind_pts)
    prox_pairs = prox_tree.query_pairs(r=0.03, output_type="ndarray")
    bind_dist = np.linalg.norm(
        bind_pts[prox_pairs[:, 0]] - bind_pts[prox_pairs[:, 1]], axis=1)
    clips_all = [str(a.name) for a in rigged.animations]
    worst_growth = 0.0
    worst_clip = ""
    growth_p99 = 0.0
    for clip in clips_all:
        anim = next(a for a in rigged.animations if str(a.name) == clip)
        length = float(getattr(anim, "length", 0.0) or 0.0)
        for frac in (0.25, 0.55, 0.85):
            arrays, _pose = deformed_parts(rigged, parts, clip, length * frac)
            posed = np.concatenate([a for a, _f in arrays])
            posed_dist = np.linalg.norm(
                posed[prox_pairs[:, 0]] - posed[prox_pairs[:, 1]], axis=1)
            growth = posed_dist - bind_dist
            gmax = float(growth.max()) if growth.size else 0.0
            if gmax > worst_growth:
                worst_growth, worst_clip = gmax, f"{clip}@{frac:.2f}"
            growth_p99 = max(
                growth_p99,
                float(np.percentile(growth, 99)) if growth.size else 0.0)
    print(f"cross-shell divergence: {len(prox_pairs)} bind-proximal pairs, "
          f"worst_growth={worst_growth:.3f} ({worst_clip}), p99={growth_p99:.3f}")
    assert worst_growth < CROSS_SHELL_MAX_GROWTH, (
        f"layered-shell tear: {worst_growth:.3f} at {worst_clip} "
        f"(limit {CROSS_SHELL_MAX_GROWTH})"
    )
    # restore the FULL inventory after the subset-gated checks
    rigged.animations = all_animations

    # ---- visual confirmation renders ---------------------------------------
    rest_world = {
        str(n.name or ""): tuple(node_world_position(n))
        for n in rigged.all_nodes()
    }
    segs = skeleton_segments(rigged, rest_world)
    bind_arrays = [
        (np.asarray([tuple(float(c) for c in v[:3]) for v in p.vertices]),
         list(p.faces))
        for p in parts
    ]
    fit_png = OUT / f"{resref}_fit_overlay.png"
    render_overlay(
        fit_png, bind_arrays, segs,
        f"{spec['display']} — auto-fit: mesh + K1 c_ithorian skeleton (bind pose)")
    print(f"visual: {fit_png.name}")

    clips = [str(a.name) for a in rigged.animations]
    picks = [c for c in ("c2a1", "g0a1", "creadyr", "cwalk") if c in clips]
    if not picks:
        picks = clips[:3]
    anim_pngs = []
    for clip in picks[:3]:
        anim = next(a for a in rigged.animations if str(a.name) == clip)
        t = max(0.0, float(getattr(anim, "length", 0.0)) * 0.45)
        arrays, pose_world = deformed_parts(rigged, parts, clip, t)
        segs_a = skeleton_segments(rigged, pose_world)
        png = OUT / f"{resref}_anim_{clip}.png"
        render_overlay(
            png, arrays, segs_a,
            f"{spec['display']} — '{clip}' @ {t:.2f}s (production skinning path)")
        anim_pngs.append(png.name)
        print(f"visual: {png.name}")

    # ---- resref rename (geometry-header name ONLY, T2538) ------------------
    old_name = str(rigged.name)
    rigged.name = resref
    print(f"resref rename: header '{old_name}' -> '{resref}' "
          f"(root node + anim_root stay '{old_name}')")

    # The OBJ material name ('IthorianSithLord_basecolor', 25 chars) exceeds
    # the MDL 16-char texture field; the writer would truncate it and the
    # export transaction's readback verification then fails on the changed
    # reference.  Point every payload skin at the final <=16-char package
    # texture name before writing.
    body_tex_name = f"{resref}_t00"
    for part in parts:
        part.texture = body_tex_name   # texture_clean derives from this
        # the reload contract digests texture_names too
        if getattr(part, "texture_names", None):
            part.texture_names = [body_tex_name]
    print(f"texture ref: payload skins -> {body_tex_name}")

    result = wf.export_scene(scene, formats=["kotor"], out_dir=str(OUT),
                             write_sidecar=True)
    rows = list(getattr(result, "formats", []) or [])
    for row in rows:
        print(f"  [{row.key}] ok={row.ok} {row.message[:120]}")
    kotor_rows = [r for r in rows if r.key == "kotor"]
    assert kotor_rows and kotor_rows[0].ok, "kotor export failed"

    mdl = OUT / f"{resref}.mdl"
    mdx = OUT / f"{resref}.mdx"
    assert mdl.is_file() and mdx.is_file()

    from src.core.game.kotor_loader import load_model_from_bytes
    initial_mdl = mdl.read_bytes()
    initial_mdx = mdx.read_bytes()
    cache_context = _set_set4_saber_disk_cache_context(
        initial_mdl, initial_mdx)
    print(
        "Set 4 plan checkpoint identity: "
        f"mdl={cache_context['initial_mdl_sha256'][:12]} "
        f"policy={cache_context['solver_policy_sha256'][:12]}")
    reloaded = load_model_from_bytes(initial_mdl, initial_mdx)
    assert reloaded is not None
    hook_contract = assert_hand_attachment_hook_contract(reloaded)
    print(f"weapon attachment hooks: {hook_contract}")
    internal_name = mdl.read_bytes()[20:52].split(b"\x00", 1)[0].decode("ascii", "replace")
    assert internal_name.lower() == resref, (internal_name, resref)
    root_name = str(reloaded.root_node.name)
    reloaded_clips = {str(a.name or "").lower() for a in reloaded.animations}
    for combat_clip in ("g0a1", "g0a2", "creadyr", "c2a1", "castout1"):
        assert combat_clip.lower() in reloaded_clips, (
            f"combat clip {combat_clip} lost in export"
        )
    anim_roots = {str(getattr(a, "anim_root", "")) for a in reloaded.animations}
    assert anim_roots <= {root_name}, (anim_roots, root_name)
    reloaded_parts = [
        n for n in reloaded.all_nodes()
        if getattr(n, "is_skin", False) and getattr(n, "vertices", None)
        and getattr(n, "bone_map", None)
    ]
    reload_checked, reload_error = assert_inverse_bind_contract(
        reloaded, reloaded_parts, node_indexed=True)
    texs = sorted({
        str(getattr(n, "texture", "") or "") for n in reloaded.all_nodes()
        if getattr(n, "is_skin", False)
    })
    print(f"reload: header={internal_name} anims={len(reloaded.animations)} "
          f"bind rows={reload_checked} err={reload_error:.3g} textures={texs}")
    body_tex = next((t for t in texs if t.lower().startswith(resref)), None)
    assert body_tex, f"no {resref}* texture reference: {texs}"

    # T2568/T2569: the clamp plateaued because a one-joint collision response cannot
    # make a long two-segment Ithorian arm reproduce a humanoid hand endpoint.
    # Solve the named saber/Force clips on the RELOADED model (the export
    # transaction relocates animation data), in animated torsoUpr space, then
    # raw-rewrite once.  First restore the target-native upright neck/head
    # posture so the hand clearance solve sees the raised Ithorian skull.
    # Native Ithorian clips and unrelated inventory stay
    # byte-semantically untouched.
    source_map = effective_animation_source_map(mgr)
    upright_head_locals, upright_head_clip, upright_head_time = _upright_head_posture_locals(
        reloaded)
    print(
        f"combat head posture reference: {upright_head_clip}@{upright_head_time:.2f}s")
    post_head_keys = 0
    post_head_reports = {}
    post_ik_keys = 0
    post_ik_reports = {}
    post_policy_keys = 0
    post_policy_reports = {}
    for post_anim in reloaded.animations:
        clip_name = str(post_anim.name or "").strip().lower()
        if clip_name not in COMBAT_HEAD_POSTURE_CLIPS and clip_name not in ARM_POSITION_GOAL_CLIPS:
            continue
        if clip_name in COMBAT_HEAD_POSTURE_CLIPS:
            head_report = retarget_combat_head_posture(
                post_anim, reloaded, upright_head_locals)
            post_head_reports[clip_name] = head_report
            post_head_keys += int(head_report["keys"])
            print(
                f"  head posture {clip_name}: "
                f"{head_report['solve_times']} samples, {head_report['keys']} keys")
        if clip_name not in ARM_POSITION_GOAL_CLIPS:
            continue
        source = source_map.get(clip_name)
        assert source is not None, f"no Dark Jedi arm source for {clip_name}"
        source_model, source_clip_name = source
        report = retarget_combat_arm_position_goals(
            post_anim, reloaded, source_model, source_clip_name)
        post_ik_reports[clip_name] = report
        post_ik_keys += int(report["keys"])
        print(
            f"  arm IK {clip_name}<-{source_clip_name}: "
            f"{report['solve_times']} samples, {report['projected']} reach clamps, "
            f"max projection {report['max_projection']:.3f}m, "
            f"saber goal/hand {report['max_saber_forward_shift']:.3f}/"
            f"{report['max_saber_hand_shift']:.3f}m, "
            f"elbow pole {report['max_elbow_pole_bias']:.3f}m")

    # T2570 phase two: ready references above must already contain their full
    # target-native head/IK corrections before transition clips blend toward
    # them.  Only orientation owners are touched; root/torso translations and
    # the authored middle of parries/get-up remain unchanged.
    animation_by_name = {
        str(anim.name or "").strip().lower(): anim for anim in reloaded.animations
    }
    for clip_name, policy in TRANSIENT_CLEARANCE_POSE_CLIPS.items():
        reference_name = str(policy["reference"])
        reference_fraction = float(policy["reference_fraction"])
        start_fraction = float(policy["start_fraction"])
        full_start_fraction = float(policy["full_start_fraction"])
        full_end_fraction = float(policy["full_end_fraction"])
        end_fraction = float(policy["end_fraction"])
        scopes = tuple(policy["scopes"])
        post_anim = animation_by_name[clip_name]
        reference_anim = animation_by_name[reference_name]
        nodes = _policy_orientation_nodes(scopes)
        report = blend_animation_orientations_to_reference(
            post_anim,
            reloaded,
            reference_anim,
            nodes,
            lambda fraction, start=start_fraction,
                    full_start=full_start_fraction,
                    full_end=full_end_fraction, end=end_fraction:
                _transient_hold_weight(
                    fraction, start, full_start, full_end, end),
            dense_ranges=(
                (start_fraction, full_start_fraction),
                (full_start_fraction, full_end_fraction),
                (full_end_fraction, end_fraction),
            ),
            reference_fraction=reference_fraction,
        )
        report.update({
            "kind": "transient_clearance",
            "reference": reference_name,
            "reference_fraction": reference_fraction,
            "start_fraction": start_fraction,
            "full_start_fraction": full_start_fraction,
            "full_end_fraction": full_end_fraction,
            "end_fraction": end_fraction,
            "scopes": scopes,
        })
        post_policy_reports[clip_name] = report
        post_policy_keys += int(report["keys"])
        print(
            f"  transient clearance {clip_name}->{reference_name} end pose "
            f"{'+'.join(scopes)}: {report['solve_times']} samples, "
            f"full {full_start_fraction:.0%}-{full_end_fraction:.0%}")

    for clip_name, reference_name in PARRY_HEAD_REFERENCE_CLIPS.items():
        post_anim = animation_by_name[clip_name]
        reference_anim = animation_by_name[reference_name]
        nodes = _policy_orientation_nodes(("head",))
        report = blend_animation_orientations_to_reference(
            post_anim,
            reloaded,
            reference_anim,
            nodes,
            _parry_head_edge_weight,
            dense_ranges=(
                (0.0, 0.20), (0.20, 0.40),
                (0.75, 0.95), (0.95, 1.0),
            ),
        )
        report.update({
            "kind": "parry_edges",
            "reference": reference_name,
            "scopes": ("head",),
        })
        post_policy_reports[clip_name] = report
        post_policy_keys += int(report["keys"])
        print(
            f"  parry head edges {clip_name}->{reference_name}: "
            f"{report['solve_times']} samples, {report['active_keys']} active keys")

    for clip_name, (reference_name, scopes) in READY_ENDPOINT_MATCH_CLIPS.items():
        post_anim = animation_by_name[clip_name]
        reference_anim = animation_by_name[reference_name]
        nodes = _policy_orientation_nodes(scopes)
        report = blend_animation_orientations_to_reference(
            post_anim,
            reloaded,
            reference_anim,
            nodes,
            lambda fraction: _smoothstep(fraction, 0.75, 0.95),
            dense_ranges=((0.75, 0.95), (0.95, 1.0)),
        )
        report.update({
            "kind": "ready_endpoint",
            "reference": reference_name,
            "scopes": tuple(scopes),
        })
        post_policy_reports[clip_name] = report
        post_policy_keys += int(report["keys"])
        print(
            f"  ready endpoint {clip_name}->{reference_name} "
            f"{'+'.join(scopes)}: {report['solve_times']} samples")

    for clip_name, policy in LATE_READY_BLEND_CLIPS.items():
        reference_name = policy["reference"]
        start_fraction = float(policy["start_fraction"])
        clearance_fraction = float(policy["clearance_fraction"])
        full_fraction = float(policy["full_fraction"])
        scopes = tuple(policy["scopes"])
        post_anim = animation_by_name[clip_name]
        reference_anim = animation_by_name[reference_name]
        component_reports = []
        if "head" in scopes:
            head_nodes = _policy_orientation_nodes(("head",))
            component_reports.append(blend_animation_orientations_to_reference(
                post_anim,
                reloaded,
                reference_anim,
                head_nodes,
                lambda fraction, start=start_fraction, end=full_fraction:
                    _smoothstep(fraction, start, end),
                dense_ranges=(
                    (start_fraction, full_fraction),
                    (full_fraction, 1.0),
                ),
            ))
        if "arms" in scopes:
            component_reports.append(blend_animation_arm_goals_to_reference(
                post_anim,
                reloaded,
                reference_anim,
                start_fraction=start_fraction,
                clearance_fraction=clearance_fraction,
                full_fraction=full_fraction,
            ))
        nodes = _policy_orientation_nodes(scopes)
        report = {
            "kind": "late_ready",
            "reference": reference_name,
            "scopes": scopes,
            "start_fraction": start_fraction,
            "full_fraction": full_fraction,
            "clearance_fraction": clearance_fraction,
            "nodes": nodes,
            "solve_times": max(
                int(component["solve_times"])
                for component in component_reports
            ),
            "keys": sum(
                int(component["keys"]) for component in component_reports),
            "active_keys": sum(
                int(component["active_keys"])
                for component in component_reports),
            "components": tuple(component_reports),
        }
        post_policy_reports[clip_name] = report
        post_policy_keys += int(report["keys"])
        print(
            f"  late ready {clip_name}->{reference_name} "
            f"{'+'.join(scopes)}: {report['solve_times']} samples, "
            f"blend {start_fraction:.0%}-{full_fraction:.0%}, "
            f"clear by {clearance_fraction:.0%}")

    native_state_alias_reports = install_modeltype_f_native_state_aliases(reloaded)
    print(
        "modeltype-F native state aliases: "
        + ", ".join(
            f"{target}<-{details['source']}"
            for target, details in native_state_alias_reports.items()
        )
    )

    if post_head_keys or post_ik_keys or post_policy_keys or native_state_alias_reports:
        from src.core.mdl.mdl_writer import MDLBinaryWriter
        raw_mdl, raw_mdx = MDLBinaryWriter().write(reloaded)
        mdl.write_bytes(raw_mdl)
        mdx.write_bytes(raw_mdx)
        reloaded_check = load_model_from_bytes(mdl.read_bytes(), mdx.read_bytes())
        assert reloaded_check is not None
        assert_hand_attachment_hook_contract(reloaded_check)
        from src.core.animation.animation_engine import mark_controller_times_sorted_for_sampling
        marked_controller_count = sum(
            1
            for check_anim in reloaded_check.animations or []
            for check_node in check_anim.nodes or []
            for check_ctrl in check_node.controllers or []
            if mark_controller_times_sorted_for_sampling(check_ctrl)
        )
        print(
            f"  reload sampling fast path: {marked_controller_count} sorted controllers")
        assert len(reloaded_check.animations) == len(reloaded.animations)
        internal2 = mdl.read_bytes()[20:52].split(b"\x00", 1)[0].decode("ascii", "replace")
        assert internal2.lower() == resref, internal2
        # Writer-facing invariants: no duplicate/out-of-range solve times and
        # no stale two-column compressed quaternion metadata on touched tracks.
        for check_anim in reloaded_check.animations:
            check_name = str(check_anim.name or "").strip().lower()
            if (check_name not in post_ik_reports
                    and check_name not in post_head_reports
                    and check_name not in post_policy_reports):
                continue
            touched_nodes = set()
            if check_name in post_head_reports:
                touched_nodes.update(COMBAT_HEAD_POSTURE_NODES)
            if check_name in post_ik_reports:
                touched_nodes.update(ARM_POSITION_GOAL_NODES)
            if check_name in post_policy_reports:
                touched_nodes.update(post_policy_reports[check_name]["nodes"])
            for check_node in check_anim.nodes or []:
                node_name = str(check_node.name or "").strip().lower()
                if node_name not in touched_nodes:
                    continue
                check_ctrl = _orientation_controller(check_node)
                assert check_ctrl is not None, (check_name, node_name)
                check_times = [float(t) for t in (check_ctrl.get("times") or [])]
                assert all(b > a for a, b in zip(check_times, check_times[1:])), (
                    check_name, node_name, "non-increasing orientation times")
                assert all(0.0 <= t <= float(check_anim.length) for t in check_times), (
                    check_name, node_name, "orientation time outside clip")
                assert int(check_ctrl.get("columns", 4)) == 4
                assert int(check_ctrl.get("binary_column_count", 4)) == 4
        acceptance_clips = {"c2a1", "c2a2", "c2a6", "g0a1", "g0a2", "creadyr"}
        for check_anim in reloaded_check.animations:
            check_name = str(check_anim.name or "").strip().lower()
            if check_name not in post_head_reports:
                continue
            audit = audit_combat_head_posture(check_anim, reloaded_check)
            print(
                f"  head posture audit {check_name}: head z "
                f"{audit['min_head_z']:.3f}m, forward "
                f"{audit['min_forward_y']:.3f}, pitch "
                f"{audit['min_forward_z']:.3f}")
            assert audit["min_head_z"] >= 0.36, (check_name, audit)
            assert audit["min_forward_y"] >= 0.90, (check_name, audit)
            assert audit["min_forward_z"] >= 0.08, (check_name, audit)
            if check_name in {"c4n1", "c4n2"}:
                # The Scholar's native neck chain is 5.8cm shorter than the
                # Lord's (upright head z 0.416m versus 0.474m), so use the
                # strict threshold both target-native rigs can satisfy.
                assert audit["min_head_z"] >= 0.40, (check_name, audit)
                assert audit["min_forward_y"] >= 0.95, (check_name, audit)
                assert audit["min_forward_z"] <= 0.30, (check_name, audit)
                assert audit["max_abs_side"] <= 0.05, (check_name, audit)

        check_by_name = {
            str(anim.name or "").strip().lower(): anim
            for anim in reloaded_check.animations
        }
        for target_name, source_name in MODELTYPE_F_NATIVE_STATE_ALIASES.items():
            assert _animation_payload_signature(
                check_by_name[target_name]
            ) == _animation_payload_signature(check_by_name[source_name]), (
                target_name, source_name, "native state alias changed after serialization")
        for check_name in sorted(MALAK_DIRECT_SAFE_DEFEND_CLIPS):
            blade_clearance = audit_saber_head_surface_clearance(
                check_by_name[check_name],
                reloaded_check,
                start_fraction=0.0,
                end_fraction=1.0,
                extra_fractions=(0.02, 0.20, 0.40, 0.60, 0.80, 0.98),
                sample_rate=240.0,
            )
            print(
                f"  direct Malak guard {check_name}: blade/head minimum "
                f"{blade_clearance['min_clearance']:.3f}m at "
                f"{blade_clearance['min_fraction']:.1%}")
            assert (
                blade_clearance["min_clearance"]
                >= RIGHT_SABER_HEAD_CLEARANCE_MIN
            ), (check_name, blade_clearance)
        for check_name, report in post_policy_reports.items():
            check_anim = check_by_name[check_name]
            reference_anim = check_by_name[report["reference"]]
            if report["kind"] == "parry_edges":
                fractions = (0.0, 0.02, 0.20, 0.95, 0.98, 1.0)
            elif report["kind"] == "ready_endpoint":
                fractions = (0.95, 0.98, 1.0)
            elif report["kind"] == "transient_clearance":
                fractions = (
                    float(report["full_start_fraction"]),
                    0.5 * (
                        float(report["full_start_fraction"])
                        + float(report["full_end_fraction"])),
                    float(report["full_end_fraction"]),
                )
            else:
                fractions = (0.90, 0.95, 1.0)
            seam = audit_orientation_reference_match(
                check_anim,
                reference_anim,
                reloaded_check,
                report["nodes"],
                fractions,
                reference_fraction=float(
                    report.get("reference_fraction", 0.0)),
            )
            print(
                f"  pose seam {check_name}->{report['reference']}: "
                f"{seam['max_angle_degrees']:.4f} degrees")
            # Binary quaternion round-tripping introduces about 0.16 degrees
            # on these tracks; keep the seam gate far below visual motion while
            # allowing that measured writer precision.
            assert seam["max_angle_degrees"] <= 0.25, (check_name, seam)
            if "head" in report["scopes"]:
                edge_start = 0.0 if report["kind"] == "parry_edges" else 0.90
                edge_end = 0.20 if report["kind"] == "parry_edges" else 1.0
                head_audit = audit_combat_head_posture(
                    check_anim,
                    reloaded_check,
                    start_fraction=edge_start,
                    end_fraction=edge_end,
                )
                assert head_audit["min_head_z"] >= 0.36, (check_name, head_audit)
                assert head_audit["min_forward_y"] >= 0.90, (check_name, head_audit)
                assert head_audit["min_forward_z"] >= 0.08, (check_name, head_audit)
                if report["kind"] == "parry_edges":
                    tail_audit = audit_combat_head_posture(
                        check_anim,
                        reloaded_check,
                        start_fraction=0.95,
                        end_fraction=1.0,
                    )
                    assert tail_audit["min_head_z"] >= 0.36, (check_name, tail_audit)
                    assert tail_audit["min_forward_y"] >= 0.90, (check_name, tail_audit)
                    assert tail_audit["min_forward_z"] >= 0.08, (check_name, tail_audit)
            if "arms" in report["scopes"]:
                clearance_start = (
                    float(report.get("clearance_fraction", 0.0))
                    if report["kind"] == "late_ready" else 0.0
                )
                clearance = audit_arm_torso_clearance(
                    check_anim,
                    reloaded_check,
                    start_fraction=clearance_start,
                    end_fraction=1.0,
                )
                print(
                    f"  pose clearance {check_name}: "
                    f"{clearance['torso_violations']} torso violations")
                assert clearance["torso_violations"] == 0, (check_name, clearance)
                if report["kind"] == "transient_clearance":
                    blade_clearance = audit_saber_head_surface_clearance(
                        check_anim,
                        reloaded_check,
                        start_fraction=float(report["start_fraction"]),
                        end_fraction=float(report["end_fraction"]),
                        extra_fractions=(
                            float(report["full_start_fraction"]),
                            0.80,
                            float(report["full_end_fraction"]),
                        ),
                    )
                    print(
                        f"  saber/head surface {check_name}: minimum "
                        f"{blade_clearance['min_clearance']:.3f}m at "
                        f"{blade_clearance['min_fraction']:.1%} "
                        f"({blade_clearance['samples']} samples)")
                    assert (
                        blade_clearance["min_clearance"]
                        >= RIGHT_SABER_HEAD_CLEARANCE_MIN
                    ), (check_name, blade_clearance)
        for check_anim in reloaded_check.animations:
            check_name = str(check_anim.name or "").strip().lower()
            if check_name not in post_ik_reports:
                continue
            source_model, source_clip_name = source_map[check_name]
            uses_coupled_surface = bool(
                post_ik_reports[check_name].get("coupled_surface"))
            uses_set4_surface = bool(
                post_ik_reports[check_name].get("set4_surface"))
            goal_end_fraction = 1.0
            endpoint_policy = READY_ENDPOINT_MATCH_CLIPS.get(check_name)
            if endpoint_policy is not None and "arms" in endpoint_policy[1]:
                goal_end_fraction = 0.75
            transient_policy = TRANSIENT_CLEARANCE_POSE_CLIPS.get(check_name)
            if transient_policy is not None:
                # The collision overlay intentionally replaces the donor arm
                # goals only inside its C1 window.  Retain the canonical 30 Hz
                # grid and filter that window instead of splitting at 70/90%:
                # those fractional boundaries are off-grid and manufacture a
                # nonlinear interpolation error the unchanged clip also has.
                audit = audit_combat_arm_position_goals(
                    check_anim,
                    reloaded_check,
                    source_model,
                    source_clip_name,
                    skip_position_goals=(
                        uses_coupled_surface or uses_set4_surface),
                    exclude_fraction_ranges=((
                        float(transient_policy["start_fraction"]),
                        float(transient_policy["end_fraction"]),
                    ),),
                )
            else:
                audit = audit_combat_arm_position_goals(
                    check_anim,
                    reloaded_check,
                    source_model,
                    source_clip_name,
                    end_fraction=goal_end_fraction,
                    skip_position_goals=(
                        uses_coupled_surface or uses_set4_surface),
                )
            clearance = audit_arm_torso_clearance(
                check_anim,
                reloaded_check,
                sample_rate=(
                    2.0 * float(COUPLED_BAKE_RATE_BY_CLIP.get(
                        check_name, 240.0))
                    if uses_coupled_surface
                    else 120.0 if uses_set4_surface else 30.0),
            )
            print(
                f"  arm IK audit {check_name}: max error "
                f"{audit['max_landing_error']:.4f}m, torso violations "
                f"{clearance['torso_violations']}, saber/head clearance "
                f"{audit['saber_head_clearance']:.3f}m")
            assert audit["max_landing_error"] <= 0.003, (check_name, audit)
            assert clearance["torso_violations"] == 0, (check_name, clearance)
            if uses_set4_surface:
                blade_clearance = audit_saber_head_surface_clearance(
                    check_anim,
                    reloaded_check,
                    start_fraction=0.0,
                    end_fraction=1.0,
                    extra_fractions=(
                        0.02, 0.20, 0.40, 0.4318, 0.60, 0.80, 0.98),
                    sample_rate=120.0,
                )
                print(
                    f"  Set 4 blade/head {check_name}: minimum "
                    f"{blade_clearance['min_clearance']:.3f}m at "
                    f"{blade_clearance['min_fraction']:.1%}")
                assert (
                    blade_clearance["min_clearance"]
                    >= RIGHT_SABER_HEAD_CLEARANCE_MIN
                ), (check_name, blade_clearance)
                if _set4_saber_required_body_clearance(
                        source_clip_name) > 0.0:
                    body_clearance = (
                        audit_saber_core_body_surface_clearance(
                            check_anim,
                            reloaded_check,
                            start_fraction=0.0,
                            end_fraction=1.0,
                            extra_fractions=(
                                SET4_BODY_SURFACE_REVIEW_FRACTIONS),
                            sample_rate=120.0,
                        )
                    )
                    print(
                        f"  Set 4 blade/body {check_name}: minimum "
                        f"{body_clearance['min_clearance']:.3f}m at "
                        f"{body_clearance['min_fraction']:.1%} "
                        f"({body_clearance['samples']} samples, "
                        f"{body_clearance['surface_faces']} faces)")
                    assert (
                        body_clearance["min_clearance"]
                        >= RIGHT_SABER_BODY_CLEARANCE_MIN
                    ), (check_name, body_clearance)
            if uses_coupled_surface:
                blade_clearance = audit_saber_head_surface_clearance(
                    check_anim,
                    reloaded_check,
                    start_fraction=0.0,
                    end_fraction=1.0,
                    extra_fractions=(0.02, 0.20, 0.40, 0.60, 0.80, 0.98),
                    sample_rate=2.0 * float(
                        COUPLED_BAKE_RATE_BY_CLIP.get(check_name, 240.0)),
                )
                elbow_order = audit_elbow_below_wrist(
                    check_anim,
                    reloaded_check,
                    "l",
                    start_fraction=0.0,
                    end_fraction=1.0,
                    extra_fractions=(0.02, 0.20, 0.40, 0.60, 0.80, 0.98),
                    sample_rate=2.0 * float(
                        COUPLED_BAKE_RATE_BY_CLIP.get(check_name, 240.0)),
                )
                grip_audit = audit_grip_against_baseline(
                    check_anim,
                    reloaded_check,
                    post_ik_reports[check_name]["dense_grip_baseline"],
                )
                print(
                    f"  defend silhouette {check_name}: blade/head minimum "
                    f"{blade_clearance['min_clearance']:.3f}m at "
                    f"{blade_clearance['min_fraction']:.1%}; wrist minimum "
                    f"{elbow_order['min_wrist_above_elbow']:.3f}m above elbow; "
                    f"grip error {grip_audit['max_grip_vector_error']:.4f}m")
                assert (
                    blade_clearance["min_clearance"]
                    >= RIGHT_SABER_HEAD_CLEARANCE_MIN
                ), (check_name, blade_clearance)
                assert grip_audit["max_grip_vector_error"] <= float(
                    COUPLED_GRIP_DRIFT_LIMIT_BY_CLIP.get(
                        check_name, 0.01)), (check_name, grip_audit)
            # The legacy joint-distance approximation predates the exact
            # posed head-surface gate above and becomes negative for the
            # deliberately raised Ithorian skull.  Set 4 clips must pass the
            # stricter 120 Hz triangle-surface audit instead.
            if (check_name in {"c2a1", "c2a2"}
                    and not uses_set4_surface):
                assert audit["saber_head_clearance"] >= 0.10, (check_name, audit)
            if check_name == "c2a1" and not uses_set4_surface:
                elbow_order = audit_elbow_below_wrist(
                    check_anim,
                    reloaded_check,
                    "l",
                    start_fraction=0.45,
                    end_fraction=0.70,
                    extra_fractions=(0.45, 0.52, 0.60, 0.62, 0.70),
                )
                print(
                    "  c2a1 left-elbow silhouette: wrist minimum "
                    f"{elbow_order['min_wrist_above_elbow']:.3f}m above elbow "
                    f"({elbow_order['samples']} samples)")
                assert elbow_order["min_wrist_above_elbow"] >= 0.05, (
                    check_name, elbow_order)
    print(
        f"post-export head posture: {post_head_keys} keys; "
        f"torso-space arm IK: {post_ik_keys} keys; "
        f"transition policy: {post_policy_keys} keys in shipped file")

    # ---- texture: 4096 JPG -> <=2048 V-flipped TGA (T2551/T2552) -----------
    from PIL import Image, ImageOps
    dst_tga = OUT / f"{body_tex.lower()}.tga"
    img = Image.open(spec["tex"]).convert("RGBA")
    if max(img.size) > KOTOR_MAX_TEX:
        img = img.resize((KOTOR_MAX_TEX, KOTOR_MAX_TEX), Image.LANCZOS)
    img = ImageOps.flip(img)
    img.save(dst_tga)
    tw, th = struct.unpack_from("<HH", dst_tga.read_bytes(), 12)
    assert max(tw, th) <= KOTOR_MAX_TEX
    print(f"texture: {dst_tga.name} {tw}x{th} V-flipped")

    return {
        "resref": resref,
        "mdl": mdl.name,
        "mdx": mdx.name,
        "tga": dst_tga.name,
        "fit_render": fit_png.name,
        "anim_renders": anim_pngs,
    }


def rebuild_lorum_appearance_only(mgr: ResourceManager | None = None) -> dict[str, int]:
    """Rebuild the package appearance row without re-exporting the MDL/MDX."""

    OUT.mkdir(parents=True, exist_ok=True)
    if mgr is None:
        mgr = ResourceManager()
        assert mgr.set_k1_dir(K1), "K1 index failed"
    inst = mgr.get_k1()
    vanilla_2da = (
        inst.get_bif("appearance", RES_2DA)
        if hasattr(inst, "get_bif") else None
    ) or mgr.get("appearance", RES_2DA, "K1")
    t = TwoDA.from_bytes(vanilla_2da)
    race_col = t.col_index("race")
    label_col = t.col_index("label")
    modeltype_col = t.col_index("modeltype")
    racetex_col = t.col_index("racetex") if "racetex" in t.columns else None
    for spec in VARIANTS:
        existing = [
            i for i in range(len(t))
            if (t.get(i, "race") or "").lower() == spec["resref"]
        ]
        assert not existing, f"vanilla 2DA already has {spec['resref']} rows {existing}"
    new_rows = {}
    for spec in VARIANTS:
        idx = len(t)
        t._rows.append(list(t._rows[APPEARANCE_TEMPLATE_ROW]))
        t._rows[idx][race_col] = spec["resref"]
        t._rows[idx][label_col] = spec["label"]
        t._rows[idx][modeltype_col] = LORUM_MODELTYPE
        if racetex_col is not None:
            t._rows[idx][racetex_col] = ""   # model carries its own texture
        new_rows[spec["resref"]] = idx
    blob = twoda_to_binary_v2b(t)
    t2 = TwoDA.from_bytes(blob)
    assert len(t2) == len(t)
    for i in (0, APPEARANCE_TEMPLATE_ROW, *new_rows.values()):
        for col in t.columns:
            assert (t2.get(i, col) or "") == (t.get(i, col) or ""), (i, col)
    (OUT / "appearance.2da").write_bytes(blob)
    print(f"\nappearance.2da: rows {new_rows} ({len(blob)} B, round-trip verified)")
    manifest_path = OUT / "sith_ithorians_package.json"
    if manifest_path.is_file():
        package_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        package_manifest["appearance_modeltypes"] = {
            spec["resref"]: LORUM_MODELTYPE for spec in VARIANTS
        }
        manifest_path.write_text(
            json.dumps(package_manifest, indent=2),
            encoding="utf-8",
        )
    return new_rows


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    mgr = ResourceManager()
    assert mgr.set_k1_dir(K1), "K1 index failed"

    built = [build_variant(mgr, spec) for spec in VARIANTS]

    # ---- appearance.2da: vanilla + one row per variant ----------------------
    new_rows = rebuild_lorum_appearance_only(mgr)

    # ---- UTC: balanced combat-ready Lorum Ipsat (T2571) ---------------------
    rebuild_lorum_utc_only(new_rows)

    deploy_files = {
        "appearance.2da",
        *(f"{spec['resref']}.{extension}" for spec in VARIANTS
          for extension in ("mdl", "mdx")),
        *(f"{spec['resref']}_t00.tga" for spec in VARIANTS),
        *(f"{spec['utc']}.utc" for spec in VARIANTS),
    }
    active_files = set(deploy_files)
    active_files.add("sith_ithorians_package.json")
    for result in built:
        for key in ("fit_render",):
            if result.get(key):
                active_files.add(str(result[key]))
        active_files.update(str(name) for name in result.get("anim_renders", ()))
        resref = str(result["resref"])
        for candidate in (
            f"{resref}.ghostrig.json",
            f"{resref}_animation_audit.json",
            f"{resref}_validation_report.json",
            f"{resref}_validation_report.txt",
        ):
            if (OUT / candidate).is_file():
                active_files.add(candidate)

    manifest = {
        "game": "K1",
        "donor": DONOR,
        "scope": {
            "active_variants": [spec["resref"] for spec in VARIANTS],
            "historical_output_files_preserved": True,
        },
        "appearance_rows": new_rows,
        "appearance_modeltypes": {
            spec["resref"]: LORUM_MODELTYPE for spec in VARIANTS
        },
        "combat_set": {
            "requested": "N_DarthMalak",
            "donor": MALAK_COMBAT_DONOR,
            "engine_slots": dict(COMBAT_ALIAS_SOURCES),
            "malak_payload_overrides": dict(
                sorted(MALAK_COMBAT_SLOT_SOURCES.items())),
            "optional_set4_inventory_mappings": dict(
                sorted(ANIMATION_SOURCE_OVERRIDES.items())),
        },
        "lorum_utc": {
            "template": "sithlord01",
            "name": "Lorum Ipsat",
            "class": 3,
            "level": 8,
            "challenge_rating": 8,
            "force_powers": list(LORUM_FORCE_POWER_IDS),
            "feats": list(LORUM_FEAT_IDS),
            "soundset": LORUM_ITHORIAN_SOUNDSET,
            "saber": LORUM_RED_SABER,
        },
        "variants": built,
        "deploy_files": sorted(deploy_files),
        "files": sorted(active_files),
    }
    (OUT / "sith_ithorians_package.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    print("package manifest written:", OUT / "sith_ithorians_package.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
