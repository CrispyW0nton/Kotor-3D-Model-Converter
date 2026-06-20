"""Joint-dot color constants and bone-name classifiers."""

from __future__ import annotations

from .dependencies import QtGui, re

# ── T401: Joint-dot overlay constants ──────────────────────────────────────
# AccuRig-style color-coded joint dots painted over the mesh during character
# rigging.  Colors match the M4 roadmap spec (knowledge_base/roadmap/
# 02_roadmap_2026_05.md ─ T401):
#   center        → yellow  #FFD400  (root, hip, stomach, head, neck …)
#   center-spine  → cyan    #00D7B5  (chest, spine, torso – primary spinal column)
#   L-side        → red     #FF40 40
#   R-side        → green   #00FF7A
JOINT_DOT_COLOR_CENTER       = QtGui.QColor("#FFD400")
JOINT_DOT_COLOR_CENTER_SPINE = QtGui.QColor("#00D7B5")
JOINT_DOT_COLOR_LEFT         = QtGui.QColor("#FF4040")
JOINT_DOT_COLOR_RIGHT        = QtGui.QColor("#00FF7A")
JOINT_DOT_COLOR_KEY          = QtGui.QColor("#3A96FF")

# Bone-name classifiers.  Order matters: L/R side wins first, then spine,
# then default center.  Names are matched case-insensitively against the
# bone node's `.name`.
#
# Two side-detection strategies, OR-combined:
#   1. Direct AccuRig naming:  ``^l(shoulder|forearm|hand|thigh|calf|...)``
#      — matches `lshoulder`, `lhand`, `lthigh`, etc. (MIRROR_PAIRS roots).
#   2. Tokenised naming:        ``[_\-\.]L$`` / ``^L_`` style
#      — matches `upperarm_L`, `L_clavicle`, `bone.l`, etc.
#
# Center-spine: chest / spine / torso / ribcage / back / sternum.
_AR_BODY_PARTS = (
    r"shoulder|forearm|hand|finger|thumb|thigh|calf|ankle|toe(base)?|"
    r"leg|shin|foot|elbow|wrist|knee|clavicle|arm|breast|hip(?!$)"
)
_RE_L_SIDE = re.compile(
    rf"^l(?:{_AR_BODY_PARTS})|(?:^|[_\-\.])l(?:$|[_\-\.])",
    re.IGNORECASE,
)
_RE_R_SIDE = re.compile(
    rf"^r(?:{_AR_BODY_PARTS})|(?:^|[_\-\.])r(?:$|[_\-\.])",
    re.IGNORECASE,
)
_RE_CENTER_SPINE = re.compile(r"spine|chest|torso|ribcage|back|sternum", re.IGNORECASE)
_KEY_JOINT_RE = re.compile(
    r"^(?:"
    r"head(?:_g)?|"
    r"neck(?:lwr)?(?:_g|_\d+)?|"
    r"spine(?:_g|_\d+)?|torso(?:upr)?_g|"
    r"(?:l|r)?(?:shoulder|clavicle|collar)(?:_g)?|(?:shoulder|clavicle|collar)_(?:l|r)|"
    r"(?:l|r)?(?:elbow|forearm)(?:_g)?|(?:elbow|forearm|lowerarm)_(?:l|r)|"
    r"(?:l|r)?hand(?:_g)?|hand_(?:l|r)|"
    r"(?:l|r)?(?:knee|shin|calf)(?:_g)?|(?:knee|shin|calf)_(?:l|r)|"
    r"(?:l|r)?foot(?:t)?(?:_g)?|foot_(?:l|r)"
    r")$",
    re.IGNORECASE,
)


def _is_key_joint_name(bone_name: str) -> bool:
    return bool(_KEY_JOINT_RE.match((bone_name or "").lower()))


def _classify_joint_color(bone_name: str) -> QtGui.QColor:
    """Return the joint-dot color appropriate for *bone_name* per T401 spec.

    Resolution order:
      1. L-side / R-side prefix or `_L` / `_R` suffix tokens win first.
      2. Then center-spine tokens (chest, spine, torso, …).
      3. Default → center yellow.

    Key joints are deliberately not classified here. They keep this original
    palette fill and receive a blue accent ring in the draw layer.
    """
    if not bone_name:
        return JOINT_DOT_COLOR_CENTER
    if _RE_L_SIDE.search(bone_name):
        return JOINT_DOT_COLOR_LEFT
    if _RE_R_SIDE.search(bone_name):
        return JOINT_DOT_COLOR_RIGHT
    if _RE_CENTER_SPINE.search(bone_name):
        return JOINT_DOT_COLOR_CENTER_SPINE
    return JOINT_DOT_COLOR_CENTER

__all__ = tuple(name for name in globals() if not name.startswith("__"))
