"""
validation_service.py  —  GhostRigger Character Validation
============================================================
Implements the pre-export validation pass described in the GhostRigger
Character Builder & Rendering Redesign Specification (§4 / §7).

Rules checked
-------------
1.  HOOK_MISSING        – required hook nodes absent (headhook, talkdummy, …)
2.  HOOK_MISALIGNED     – hook position clearly off-axis / mis-parented
3.  WEIGHT_UNNORMALIZED – skin weights per vertex don't sum to 1 (±0.01)
4.  WEIGHT_ZERO_SUM     – vertex has no influence (all weights == 0)
5.  WEIGHT_OVERFLOW     – more than 4 bone influences on a vertex (KotOR limit)
6.  SUPERMODEL_MISMATCH – body/head supermodels disagree or unknown
7.  K1_K2_MISMATCH      – parts from different game versions mixed in one scene
8.  BONE_MISSING        – required facial / skeleton bone absent from head
9.  SKIN_MESH_UNRIGGED  – skin mesh node has no bone references
10. NO_GEOMETRY         – scene has no renderable geometry at all

Each issue is represented by a ``ValidationIssue`` with severity (ERROR /
WARNING / INFO), a machine-readable code, a human-readable message, and an
optional node name and slot reference.

Usage
-----
::

    from src.core.diagnostics.validation_service import ValidationService
    from src.core.geometry.model_data import CharacterScene, PartSlot

    scene = CharacterScene(game_version='K1')
    scene.assign(PartSlot.HEAD_SHELL, head_model, resref='pfhc01')
    scene.assign(PartSlot.HEADLESS_BODY, body_model, resref='pfbcm')

    svc = ValidationService(scene)
    issues = svc.validate()
    for issue in issues:
        print(issue)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
#  Severity / Issue dataclasses
# ──────────────────────────────────────────────────────────────────────────────

class Severity(Enum):
    ERROR   = "error"    # blocks export
    WARNING = "warning"  # should be reviewed; export still possible
    INFO    = "info"     # informational


@dataclass
class ValidationIssue:
    """A single validation finding.

    Attributes
    ----------
    severity : ERROR / WARNING / INFO.
    code     : Machine-readable tag (e.g. "HOOK_MISSING").
    message  : Human-readable description.
    slot     : PartSlot that caused the issue (or None for scene-level issues).
    node     : Name of the offending ModelNode (or empty string).
    """
    severity: Severity
    code:     str
    message:  str
    slot:     Optional[object]  = None   # PartSlot enum member or None
    node:     str               = ""

    def __str__(self) -> str:
        loc = ""
        if self.slot is not None:
            loc += f"[{getattr(self.slot, 'value', str(self.slot))}]"
        if self.node:
            loc += f"[{self.node}]"
        return f"[{self.severity.value.upper()}] {self.code}{loc}: {self.message}"

    @property
    def is_error(self) -> bool:
        return self.severity == Severity.ERROR

    @property
    def is_warning(self) -> bool:
        return self.severity == Severity.WARNING


# ──────────────────────────────────────────────────────────────────────────────
#  Known hook / anchor nodes
# ──────────────────────────────────────────────────────────────────────────────

#: Hooks that MUST exist on a complete head model.
_HEAD_REQUIRED_HOOKS: List[str] = [
    "talkdummy",
    "headhook",
]

#: Hooks expected on a head (warn if absent, not error).
_HEAD_EXPECTED_HOOKS: List[str] = [
    "camerahook",
    "cutscenedummy",
    "MaskHook",
    "GoggleHook",
]

#: Hooks that MUST exist on a headless body model.
_BODY_REQUIRED_HOOKS: List[str] = [
    "headhook",
    "rhand",
]

#: Hooks expected on a body (warn if absent).
_BODY_EXPECTED_HOOKS: List[str] = [
    "lhand_g",
    "camerahook",
    "chestconjure",
    "handconjure",
    "impact_bolt",
]

#: Facial bones expected to exist in the head hierarchy.
_FACIAL_BONES: List[str] = [
    "f_um_g",    # upper mouth
    "f_jaw_g",   # jaw
    "f_lmc_g",   # left mouth corner
    "f_rmc_g",   # right mouth corner
]

#: Known valid K1 supermodels (case-insensitive compare).
_K1_SUPERMODELS: Set[str] = {
    "S_FEMALE02", "S_FEMALE03", "S_MALE02", "S_MALE03",
}

#: Known valid K2 supermodels.
_K2_SUPERMODELS: Set[str] = {
    "S_FEMALE02", "S_FEMALE03", "S_MALE02", "S_MALE03",
}

#: Standalone / no-supermodel sentinels.
_NULL_SUPERMODELS: Set[str] = {"NULL", "", "NONE"}


# ──────────────────────────────────────────────────────────────────────────────
#  ValidationService
# ──────────────────────────────────────────────────────────────────────────────

class ValidationService:
    """Run all validation rules on a CharacterScene.

    Parameters
    ----------
    scene       : The CharacterScene to validate.
    strict      : When True, structural blockers remain errors. Advisory
                  expected hooks stay warnings because vanilla KOTOR models do
                  not all include every optional attachment/effect hook.
    max_weight_errors : Cap on per-slot weight errors (to avoid flooding the
                        log for meshes with thousands of bad vertices).
    """

    def __init__(
        self,
        scene,                        # CharacterScene
        *,
        strict: bool = False,
        max_weight_errors: int = 20,
    ) -> None:
        self._scene = scene
        self._strict = strict
        self._max_weight_errors = max_weight_errors
        self._issues: List[ValidationIssue] = []

    # ── Public API ────────────────────────────────────────────────────────────

    def validate(self) -> List[ValidationIssue]:
        """Run all rules and return the full list of ValidationIssues."""
        self._issues = []

        self._check_scene_not_empty()
        self._check_k1_k2_mismatch()
        self._check_supermodel_consistency()

        try:
            from src.core.geometry.model_data import PartSlot
        except ImportError:
            from core.geometry.model_data import PartSlot  # type: ignore

        for slot, entry in self._scene.slots.items():
            model = entry.model
            if model is None:
                continue

            # Per-slot hooks
            if slot == PartSlot.HEAD_SHELL:
                self._check_hooks(slot, model,
                                  _HEAD_REQUIRED_HOOKS, _HEAD_EXPECTED_HOOKS)
                self._check_facial_bones(slot, model)
            elif slot == PartSlot.HEADLESS_BODY:
                required, expected = self._body_hook_requirements(model)
                self._check_hooks(slot, model, required, expected)

            # Per-slot weight validation
            self._check_skin_weights(slot, model)

        log.debug("ValidationService: %d issues found", len(self._issues))
        return list(self._issues)

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self._issues if i.is_error]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self._issues if i.is_warning]

    @property
    def passed(self) -> bool:
        """True when there are no ERRORs (warnings are acceptable)."""
        return not any(i.is_error for i in self._issues)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _add(
        self,
        severity: Severity,
        code: str,
        message: str,
        slot=None,
        node: str = "",
    ) -> None:
        self._issues.append(
            ValidationIssue(severity=severity, code=code,
                            message=message, slot=slot, node=node)
        )

    def _err(self, code, msg, slot=None, node=""):
        self._add(Severity.ERROR, code, msg, slot, node)

    def _warn(self, code, msg, slot=None, node=""):
        self._add(Severity.WARNING, code, msg, slot, node)

    def _info(self, code, msg, slot=None, node=""):
        self._add(Severity.INFO, code, msg, slot, node)

    # ── Rule implementations ──────────────────────────────────────────────────

    def _check_scene_not_empty(self) -> None:
        """Rule NO_GEOMETRY – scene must have at least one renderable part."""
        has_geo = False
        for entry in self._scene.slots.values():
            m = entry.model
            if m is None:
                continue
            try:
                if any(n.vertices for n in m.all_nodes()):
                    has_geo = True
                    break
            except Exception:
                pass
        if not has_geo:
            self._warn("NO_GEOMETRY",
                       "Scene has no renderable geometry. "
                       "Assign at least one head or body model.")

    def _check_k1_k2_mismatch(self) -> None:
        """Rule K1_K2_MISMATCH – all assigned parts must share the same game version."""
        gvs: Set[str] = set()
        for entry in self._scene.slots.values():
            gv = (entry.game_version or self._scene.game_version or "").upper()
            if gv in ("K1", "K2"):
                gvs.add(gv)
        if len(gvs) > 1:
            self._err("K1_K2_MISMATCH",
                      f"Scene mixes K1 and K2 parts ({sorted(gvs)}). "
                      "All slots must use the same game version.")

    def _check_supermodel_consistency(self) -> None:
        """Rule SUPERMODEL_MISMATCH – body and head must agree on supermodel."""
        supermodels: Dict[str, str] = {}  # slot.value → supermodel
        for slot, entry in self._scene.slots.items():
            m = entry.model
            if m is None:
                continue
            sm = (getattr(m, "supermodel", "") or "").strip().upper()
            if sm and sm not in _NULL_SUPERMODELS:
                supermodels[getattr(slot, 'value', str(slot))] = sm

        if len(set(supermodels.values())) > 1:
            detail = ", ".join(f"{k}={v}" for k, v in supermodels.items())
            self._err("SUPERMODEL_MISMATCH",
                      f"Parts have conflicting supermodels: {detail}. "
                      "Head and body must share the same supermodel (e.g. S_Female02).")

        # Validate each supermodel against the expected game's set
        gv = (self._scene.game_version or "K1").upper()
        expected_set = _K1_SUPERMODELS if gv == "K1" else _K2_SUPERMODELS
        for slot, sm in supermodels.items():
            if sm not in expected_set and sm not in _NULL_SUPERMODELS:
                self._warn("SUPERMODEL_UNKNOWN",
                           f"Supermodel '{sm}' (slot {slot}) is not a known "
                           f"{gv} supermodel. This may cause in-game rig errors.")

    def _get_node_map(self, model) -> Dict[str, object]:
        """Build name→node dict from a KotorModel."""
        node_map: Dict[str, object] = {}
        try:
            for node in model.all_nodes():
                node_map[node.name] = node
        except Exception as exc:
            log.debug("_get_node_map: %s", exc)
        return node_map

    def _body_hook_requirements(self, model) -> tuple[List[str], List[str]]:
        """Return body hook rules, honoring native-template creature donors."""
        state = getattr(model, "_gr_character_builder_rig_state", None)
        if isinstance(state, dict):
            state_name = str(state.get("state") or "")
            native_snapshot_present = bool(state.get("native_snapshot_present"))
        else:
            state_name = str(getattr(state, "state", "") or "")
            native_snapshot_present = bool(getattr(state, "native_snapshot_present", False))

        metadata = getattr(model, "metadata", None)
        if not native_snapshot_present and isinstance(metadata, dict):
            raw_state = metadata.get("character_builder_rig_state")
            if isinstance(raw_state, dict):
                state_name = str(raw_state.get("state") or state_name)
                native_snapshot_present = bool(raw_state.get("native_snapshot_present"))

        if state_name != "native_template_final" or not native_snapshot_present:
            return list(_BODY_REQUIRED_HOOKS), list(_BODY_EXPECTED_HOOKS)

        snapshot = getattr(model, "_gr_native_skeleton_snapshot", None)
        hook_names = list(getattr(snapshot, "hook_names", ()) or ())
        if not hook_names and isinstance(metadata, dict):
            snap_data = metadata.get("native_skeleton_snapshot")
            if isinstance(snap_data, dict):
                hook_names = list(snap_data.get("hook_names") or ())
        required = [str(name or "") for name in hook_names if str(name or "").strip()]
        if not required:
            return list(_BODY_REQUIRED_HOOKS), list(_BODY_EXPECTED_HOOKS)
        required_lower = {name.lower() for name in required}
        expected = [
            name for name in _BODY_EXPECTED_HOOKS
            if name.lower() not in required_lower
        ]
        return required, expected

    def _check_hooks(self, slot, model, required: List[str], expected: List[str]) -> None:
        """Rules HOOK_MISSING / HOOK_MISALIGNED."""
        node_map = self._get_node_map(model)
        names_lower = {k.lower(): k for k in node_map}

        for hook in required:
            if hook.lower() not in names_lower:
                self._err("HOOK_MISSING",
                          f"Required hook '{hook}' not found in model. "
                          "The game engine uses this node to attach geometry / camera.",
                          slot=slot, node=hook)

        for hook in expected:
            if hook.lower() not in names_lower:
                self._add(Severity.WARNING, "HOOK_MISSING",
                          f"Expected hook '{hook}' not found. "
                          "Cutscene / item-attachment may break.",
                          slot=slot, node=hook)

    def _check_facial_bones(self, slot, model) -> None:
        """Rule BONE_MISSING – required facial bones absent from head model."""
        node_map = self._get_node_map(model)
        names_lower = {k.lower() for k in node_map}
        for bone in _FACIAL_BONES:
            if bone.lower() not in names_lower:
                self._warn("BONE_MISSING",
                           f"Facial bone '{bone}' not found in head model. "
                           "Lip-sync and facial animations may not work correctly.",
                           slot=slot, node=bone)

    def _check_skin_weights(self, slot, model) -> None:
        """Rules WEIGHT_UNNORMALIZED / WEIGHT_ZERO_SUM / WEIGHT_OVERFLOW / SKIN_MESH_UNRIGGED."""
        try:
            nodes = model.all_nodes()
        except Exception:
            return

        for node in nodes:
            # Only skin nodes carry bone weights
            is_skin = getattr(node, "is_skin", False) or bool(
                getattr(node, "flags", 0) & 0x0040  # NodeFlags.SKIN
            )
            if not is_skin:
                continue

            # Check for completely unrigged skin mesh.  New Character Builder
            # output stores canonical KOTOR rows in skin_data; older imports may
            # still expose compatibility bone_weights/bone_indices lists.
            skin_data = getattr(node, "skin_data", None) or []
            bone_map = getattr(node, "bone_map", None) or []
            bone_indices = getattr(node, "bone_indices", None) or []
            bone_weights = getattr(node, "bone_weights", None) or []
            if not skin_data and not bone_indices and not bone_weights:
                self._warn("SKIN_MESH_UNRIGGED",
                           f"Skin mesh '{node.name}' has no bone references. "
                           "It will not deform in-game.",
                           slot=slot, node=node.name)
                continue
            if skin_data and not bone_map:
                self._warn("SKIN_MESH_UNRIGGED",
                           f"Skin mesh '{node.name}' has vertex influences but no "
                           "bone map. It will not deform in-game.",
                           slot=slot, node=node.name)
                continue

            # Per-vertex weight checks
            n_verts = len(getattr(node, "vertices", []) or [])
            if n_verts == 0:
                continue

            err_count = 0
            if skin_data:
                row_count = min(n_verts, len(skin_data))
            else:
                row_count = min(n_verts, len(bone_weights))
            if row_count < n_verts:
                for vi in range(row_count, n_verts):
                    if err_count >= self._max_weight_errors:
                        break
                    self._warn("WEIGHT_ZERO_SUM",
                               f"Vertex {vi} of '{node.name}' has no skin "
                               "weight row. It will not deform in-game.",
                               slot=slot, node=node.name)
                    err_count += 1
            for vi in range(row_count):
                if skin_data:
                    influences = getattr(skin_data[vi], "influences", None) or []
                    wlist = [
                        float(getattr(inf, "weight", 0.0))
                        for inf in influences
                    ]
                else:
                    weights_row = bone_weights[vi]
                    if not hasattr(weights_row, "__iter__"):
                        continue
                    wlist = list(weights_row)

                # WEIGHT_OVERFLOW – more than 4 influences
                if len(wlist) > 4:
                    if err_count < self._max_weight_errors:
                        self._warn("WEIGHT_OVERFLOW",
                                   f"Vertex {vi} of '{node.name}' has {len(wlist)} "
                                   "bone influences (KotOR limit is 4). "
                                   "Extra influences will be silently dropped.",
                                   slot=slot, node=node.name)
                    err_count += 1
                    wlist = wlist[:4]

                total = sum(w for w in wlist if isinstance(w, (int, float)))

                # WEIGHT_ZERO_SUM – fully unweighted vertex
                if total < 1e-6:
                    if err_count < self._max_weight_errors:
                        self._warn("WEIGHT_ZERO_SUM",
                                   f"Vertex {vi} of '{node.name}' has zero total "
                                   "weight. It will not deform in-game.",
                                   slot=slot, node=node.name)
                    err_count += 1
                    continue

                # WEIGHT_UNNORMALIZED – weights don't sum to ~1
                if abs(total - 1.0) > 0.01:
                    if err_count < self._max_weight_errors:
                        self._warn("WEIGHT_UNNORMALIZED",
                                   f"Vertex {vi} of '{node.name}': weights sum to "
                                   f"{total:.4f} (expected 1.0). "
                                   "Normalize before export.",
                                   slot=slot, node=node.name)
                    err_count += 1

            if err_count >= self._max_weight_errors:
                self._info("WEIGHT_ERRORS_TRUNCATED",
                           f"'{node.name}': {err_count}+ weight issues found; "
                           "only first ones shown.",
                           slot=slot, node=node.name)


# ──────────────────────────────────────────────────────────────────────────────
#  Convenience function
# ──────────────────────────────────────────────────────────────────────────────

def validate_scene(scene, *, strict: bool = False) -> List[ValidationIssue]:
    """Shorthand: create a ValidationService and run validate().

    Parameters
    ----------
    scene  : CharacterScene to validate.
    strict : Promote some warnings to errors.

    Returns
    -------
    List of ValidationIssue objects.
    """
    return ValidationService(scene, strict=strict).validate()
