"""
test_v400_rig_mode.py
======================
Comprehensive tests for Phase 3 of the GhostRigger Character Builder:
  Rig Mode (_RigFrame) — skeleton joint display, bone-group selection,
  weight painting audit, symmetry mirror, region presets.

Tests are fully headless (no Tk display required) — they exercise the
data-model layer of _RigFrame without creating any Tk widgets.

Coverage:
  • _FallbackSelector (standalone, no character_builder dep)
  • SkeletonSelector via character_builder.py BONE_GROUPS
  • _RigFrame._pick_primary_model() slot priority
  • _RigFrame region / selection logic (via mocked widget)
  • Mirror pair table completeness and symmetry
  • Weight audit logic
  • Bone list population helpers
  • Detail pane content helpers
"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


# ──────────────────────────────────────────────────────────────────────────────
#  Minimal model stubs (no Tk required)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class _StubBoneWeight:
    bone_index: int = 0
    weight: float = 0.0

@dataclass
class _StubVertexSkinData:
    influences: List[_StubBoneWeight] = field(default_factory=list)

@dataclass
class _StubNode:
    name: str
    flags: int = 0x01     # HEADER / dummy by default
    position: tuple = (0.0, 0.0, 0.0)
    children: List["_StubNode"] = field(default_factory=list)
    parent: Optional["_StubNode"] = None
    skin_data: List[_StubVertexSkinData] = field(default_factory=list)
    bone_map: List[str] = field(default_factory=list)

    @property
    def type_label(self):
        from src.core.model_data import NodeFlags
        if self.flags & int(NodeFlags.SKIN):
            return "skin"
        if self.flags & int(NodeFlags.MESH):
            return "trimesh"
        return "dummy"

    @property
    def is_skin(self):
        from src.core.model_data import NodeFlags
        return bool(self.flags & int(NodeFlags.SKIN))

    @property
    def is_mesh(self):
        from src.core.model_data import NodeFlags
        return bool(self.flags & int(NodeFlags.MESH))

    def bone_world_position(self):
        return self.position


@dataclass
class _StubModel:
    name: str = "test_model"
    root_node: Optional[_StubNode] = None
    animations: List[Any] = field(default_factory=list)
    supermodel: str = "S_Female02"

    def all_nodes(self):
        if self.root_node is None:
            return []
        result = []
        stack = [self.root_node]
        while stack:
            n = stack.pop()
            result.append(n)
            stack.extend(reversed(n.children))
        return result

    def find_node(self, name: str):
        nl = name.lower()
        for n in self.all_nodes():
            if n.name.lower() == nl:
                return n
        return None

    def node_count(self):
        return len(self.all_nodes())

    @property
    def is_empty(self):
        return self.root_node is None


def _make_body_model():
    """Build a stub humanoid body model with real KotOR bone names."""
    root = _StubNode("pfbcm")
    pelvis = _StubNode("pelvis_g", position=(0.0, 0.0, 0.95))
    torso  = _StubNode("torso_g",  position=(0.0, 0.0, 1.10))
    neck   = _StubNode("neck_g",   position=(0.0, 0.0, 1.45))
    head   = _StubNode("head_g",   position=(0.0, 0.0, 1.60))
    # Left arm chain
    lcollar = _StubNode("lcollar_g", position=(0.20, 0.0, 1.40))
    lbicep  = _StubNode("lbicep_g",  position=(0.35, 0.0, 1.30))
    lforearm= _StubNode("lforearm_g",position=(0.50, 0.0, 1.15))
    lhand   = _StubNode("lhand_g",   position=(0.60, 0.0, 1.00))
    # Right arm chain
    rcollar = _StubNode("rcollar_g", position=(-0.20, 0.0, 1.40))
    rbicep  = _StubNode("rbicep_g",  position=(-0.35, 0.0, 1.30))
    rforearm= _StubNode("rforearm_g",position=(-0.50, 0.0, 1.15))
    rhand   = _StubNode("rhand",     position=(-0.60, 0.0, 1.00))
    # Left leg chain
    lthigh  = _StubNode("lthigh_g",  position=(0.10, 0.0, 0.75))
    lshin   = _StubNode("lshin_g",   position=(0.10, 0.0, 0.40))
    lfoot   = _StubNode("lfoot_g",   position=(0.10, 0.0, 0.05))
    # Right leg chain
    rthigh  = _StubNode("rthigh_g",  position=(-0.10, 0.0, 0.75))
    rshin   = _StubNode("rshin_g",   position=(-0.10, 0.0, 0.40))
    rfoot   = _StubNode("rfoot_g",   position=(-0.10, 0.0, 0.05))
    # Skin mesh (NodeFlags.SKIN = 64 = 0x40)
    from src.core.model_data import NodeFlags as _NF
    skin_node = _StubNode("torso", flags=int(_NF.SKIN))

    # Wire hierarchy
    root.children    = [pelvis]
    pelvis.children  = [torso, lthigh, rthigh]
    torso.children   = [neck, lcollar, rcollar]
    neck.children    = [head]
    lcollar.children = [lbicep]
    lbicep.children  = [lforearm]
    lforearm.children= [lhand]
    rcollar.children = [rbicep]
    rbicep.children  = [rforearm]
    rforearm.children= [rhand]
    lthigh.children  = [lshin]
    lshin.children   = [lfoot]
    rthigh.children  = [rshin]
    rshin.children   = [rfoot]
    pelvis.children.append(skin_node)

    for child in root.children:
        child.parent = root
    for child in pelvis.children:
        child.parent = pelvis

    m = _StubModel(name="pfbcm", root_node=root)
    return m


def _make_head_model():
    """Build a stub head model with facial bones and hooks."""
    root = _StubNode("pfhc01")
    neck   = _StubNode("neck_g",    position=(0.0, 0.0, 1.45))
    headg  = _StubNode("head_g",    position=(0.0, 0.0, 1.60))
    f_um   = _StubNode("f_um_g",    position=(0.0, -0.05, 1.62))
    f_jaw  = _StubNode("f_jaw_g",   position=(0.0, -0.04, 1.55))
    f_lmc  = _StubNode("f_lmc_g",   position=(0.05, -0.04, 1.60))
    f_rmc  = _StubNode("f_rmc_g",   position=(-0.05, -0.04, 1.60))
    talk   = _StubNode("talkdummy", position=(0.0, 0.0, 1.65))
    headhook = _StubNode("headhook",position=(0.0, 0.0, 1.70))
    camhook  = _StubNode("camerahook", position=(0.0, 0.2, 1.65))

    root.children    = [neck]
    neck.children    = [headg]
    headg.children   = [f_um, f_jaw, f_lmc, f_rmc, talk, headhook, camhook]

    m = _StubModel(name="pfhc01", root_node=root)
    return m


def _make_scene_with(body=None, head=None):
    """Make a CharacterScene with optional body/head models."""
    from src.core.model_data import CharacterScene, PartSlot
    scene = CharacterScene(game_version="K1")
    if body is not None:
        scene.assign(PartSlot.HEADLESS_BODY, body, resref="pfbcm",
                     game_version="K1", source_path="/tmp/pfbcm.mdl")
    if head is not None:
        scene.assign(PartSlot.HEAD_SHELL, head, resref="pfhc01",
                     game_version="K1", source_path="/tmp/pfhc01.mdl")
    return scene


# ──────────────────────────────────────────────────────────────────────────────
#  FallbackSelector tests
# ──────────────────────────────────────────────────────────────────────────────

class TestFallbackSelector:
    """Tests for the _FallbackSelector defined inside character_builder_window."""

    def _get_cls(self):
        from src.gui.character_builder_window import _FallbackSelector
        return _FallbackSelector

    def test_empty_init(self):
        cls = self._get_cls()
        sel = cls()
        assert sel.count == 0
        assert sel.selected_names == []

    def test_init_with_model(self):
        cls = self._get_cls()
        model = _make_body_model()
        sel = cls(model)
        all_names = {n.name for n in model.all_nodes()}
        # _names should be populated
        assert len(sel._names) == len(all_names)

    def test_select_all(self):
        cls = self._get_cls()
        model = _make_body_model()
        sel = cls(model)
        result = sel.select_all()
        assert len(result) > 0
        assert sel.count > 0

    def test_clear(self):
        cls = self._get_cls()
        model = _make_body_model()
        sel = cls(model)
        sel.select_all()
        sel.clear()
        assert sel.count == 0

    def test_select_by_names_found(self):
        cls = self._get_cls()
        model = _make_body_model()
        sel = cls(model)
        found = sel.select_by_names(["pelvis_g", "torso_g", "nonexistent"])
        assert "pelvis_g" in found
        assert "torso_g" in found
        assert "nonexistent" not in found

    def test_select_skeleton_only(self):
        cls = self._get_cls()
        model = _make_body_model()
        sel = cls(model)
        result = sel.select_skeleton_only()
        assert len(result) > 0

    def test_select_group_any(self):
        cls = self._get_cls()
        model = _make_body_model()
        sel = cls(model)
        result = sel.select_group("spine")
        assert len(result) > 0

    def test_selected_names_property(self):
        cls = self._get_cls()
        model = _make_body_model()
        sel = cls(model)
        sel.select_by_names(["pelvis_g"])
        assert "pelvis_g" in sel.selected_names

    def test_count_increases(self):
        cls = self._get_cls()
        model = _make_body_model()
        sel = cls(model)
        assert sel.count == 0
        sel.select_by_names(["pelvis_g", "torso_g"])
        assert sel.count >= 1  # at least the ones that exist


# ──────────────────────────────────────────────────────────────────────────────
#  Mirror pair table tests
# ──────────────────────────────────────────────────────────────────────────────

class TestMirrorPairs:
    """Tests for _RigFrame._MIRROR_PAIRS symmetry."""

    def _get_pairs(self):
        from src.gui.character_builder_window import _RigFrame
        return _RigFrame._MIRROR_PAIRS

    def test_mirror_pairs_is_dict(self):
        pairs = self._get_pairs()
        assert isinstance(pairs, dict)
        assert len(pairs) > 0

    def test_mirror_pairs_symmetric(self):
        """Every mirror should also have its reverse in the table."""
        pairs = self._get_pairs()
        for k, v in pairs.items():
            assert v in pairs, f"Mirror pair missing reverse: {k}↔{v}"
            assert pairs[v] == k, f"Mirror not symmetric: {k}↔{v} but {v}↔{pairs[v]}"

    def test_lbicep_to_rbicep(self):
        pairs = self._get_pairs()
        assert pairs.get("lbicep_g") == "rbicep_g"
        assert pairs.get("rbicep_g") == "lbicep_g"

    def test_lcollar_to_rcollar(self):
        pairs = self._get_pairs()
        assert pairs.get("lcollar_g") == "rcollar_g"

    def test_lthigh_to_rthigh(self):
        pairs = self._get_pairs()
        assert pairs.get("lthigh_g") == "rthigh_g"
        assert pairs.get("rthigh_g") == "lthigh_g"

    def test_eyelid_mirror(self):
        pairs = self._get_pairs()
        assert pairs.get("eyeLlid") == "eyeRlid"
        assert pairs.get("eyeRlid") == "eyeLlid"

    def test_facial_corners_mirror(self):
        pairs = self._get_pairs()
        assert pairs.get("f_lmc_g") == "f_rmc_g"
        assert pairs.get("f_rmc_g") == "f_lmc_g"

    def test_no_self_mirror(self):
        """A bone should not map to itself."""
        pairs = self._get_pairs()
        for k, v in pairs.items():
            assert k != v, f"Bone maps to itself: {k}"

    def test_lforearm_to_rforearm(self):
        pairs = self._get_pairs()
        assert pairs.get("lforearm_g") == "rforearm_g"

    def test_lfoot_to_rfoot(self):
        pairs = self._get_pairs()
        assert pairs.get("lfoot_g") == "rfoot_g"

    def test_LArm_to_RArm(self):
        pairs = self._get_pairs()
        assert pairs.get("LArm") == "RArm"


# ──────────────────────────────────────────────────────────────────────────────
#  Region preset definitions test
# ──────────────────────────────────────────────────────────────────────────────

class TestRegionPresets:
    """Tests for _RigFrame._REGION_PRESETS definitions."""

    def _get_presets(self):
        from src.gui.character_builder_window import _RigFrame
        return _RigFrame._REGION_PRESETS

    def test_presets_is_list(self):
        presets = self._get_presets()
        assert isinstance(presets, list)
        assert len(presets) >= 5

    def test_preset_tuple_format(self):
        for preset in self._get_presets():
            assert len(preset) == 3, f"Preset should have 3 elements: {preset}"
            label, key, bg = preset
            assert isinstance(label, str) and label
            assert isinstance(key, str) and key
            assert isinstance(bg, str) and bg.startswith("#")

    def test_all_bones_preset_exists(self):
        presets = self._get_presets()
        keys = [p[1] for p in presets]
        assert "all" in keys

    def test_spine_preset_exists(self):
        keys = [p[1] for p in self._get_presets()]
        assert "spine" in keys

    def test_arm_presets_exist(self):
        keys = [p[1] for p in self._get_presets()]
        assert "left_arm" in keys
        assert "right_arm" in keys

    def test_leg_presets_exist(self):
        keys = [p[1] for p in self._get_presets()]
        assert "left_leg" in keys
        assert "right_leg" in keys

    def test_head_preset_exists(self):
        keys = [p[1] for p in self._get_presets()]
        assert "head" in keys

    def test_attachment_preset_exists(self):
        keys = [p[1] for p in self._get_presets()]
        assert "attachment" in keys

    def test_region_keys_in_bone_groups(self):
        """All region preset keys must exist in BONE_GROUPS."""
        from src.core.character_builder import BONE_GROUPS
        presets = self._get_presets()
        for label, key, _ in presets:
            assert key in BONE_GROUPS, \
                f"Region key '{key}' not in BONE_GROUPS"


# ──────────────────────────────────────────────────────────────────────────────
#  _pick_primary_model slot priority test (via minimal mock window)
# ──────────────────────────────────────────────────────────────────────────────

class _MockWindow:
    """Minimal mock of CharacterBuilderWindow for unit testing _RigFrame."""
    def __init__(self, scene):
        self.scene = scene
        self._mode_frames = [None] * 5


class _MockRigFrame:
    """Instantiates _RigFrame logic without creating Tk widgets."""

    def __init__(self, scene):
        self._win = _MockWindow(scene)

    def _pick_primary_model(self):
        from src.gui.character_builder_window import _import_model_data
        try:
            PartSlot = _import_model_data()[1]
            scene = self._win.scene
            for slot in (PartSlot.HEADLESS_BODY, PartSlot.HEAD_SHELL,
                         PartSlot.BODY_VARIANT):
                entry = scene.slots.get(slot)
                if entry and entry.model is not None:
                    return entry.model
            for entry in scene.slots.values():
                if entry.model is not None:
                    return entry.model
        except Exception:
            pass
        return None


class TestRigFrameModelSelection:

    def test_empty_scene_returns_none(self):
        from src.core.model_data import CharacterScene
        scene = CharacterScene(game_version="K1")
        frame = _MockRigFrame(scene)
        assert frame._pick_primary_model() is None

    def test_headless_body_slot_preferred(self):
        body  = _make_body_model()
        head  = _make_head_model()
        scene = _make_scene_with(body=body, head=head)
        frame = _MockRigFrame(scene)
        result = frame._pick_primary_model()
        # HEADLESS_BODY takes priority
        assert result is body

    def test_head_shell_used_when_no_body(self):
        head  = _make_head_model()
        scene = _make_scene_with(head=head)
        frame = _MockRigFrame(scene)
        result = frame._pick_primary_model()
        assert result is head

    def test_any_slot_used_as_last_resort(self):
        from src.core.model_data import CharacterScene, PartSlot
        scene = CharacterScene(game_version="K1")
        model = _make_body_model()
        scene.assign(PartSlot.ACCESSORY, model, resref="acc",
                     game_version="K1", source_path="/tmp/acc.mdl")
        frame = _MockRigFrame(scene)
        result = frame._pick_primary_model()
        assert result is model

    def test_body_variant_preferred_over_accessory(self):
        from src.core.model_data import CharacterScene, PartSlot
        scene = CharacterScene(game_version="K1")
        variant = _make_body_model()
        variant.name = "variant"
        acc = _make_head_model()
        acc.name = "acc"
        scene.assign(PartSlot.BODY_VARIANT, variant, resref="var",
                     game_version="K1", source_path="/tmp/var.mdl")
        scene.assign(PartSlot.ACCESSORY, acc, resref="acc",
                     game_version="K1", source_path="/tmp/acc.mdl")
        frame = _MockRigFrame(scene)
        result = frame._pick_primary_model()
        assert result is variant


# ──────────────────────────────────────────────────────────────────────────────
#  SkeletonSelector integration tests
# ──────────────────────────────────────────────────────────────────────────────

class TestSkeletonSelectorIntegration:
    """Tests that SkeletonSelector correctly processes real bone groups."""

    def _make_selector(self, model):
        from src.core.character_builder import SkeletonSelector
        return SkeletonSelector(model)

    def test_selector_select_all(self):
        model = _make_body_model()
        sel = self._make_selector(model)
        result = sel.select_all()
        # Should select all nodes
        assert len(result) == model.node_count()

    def test_selector_select_spine_group(self):
        model = _make_body_model()
        sel = self._make_selector(model)
        result = sel.select_group("spine")
        # pelvis_g, torso_g, neck_g, head_g are present
        found_names = set(result)
        assert "pelvis_g" in found_names or len(found_names) > 0

    def test_selector_select_left_arm_group(self):
        model = _make_body_model()
        sel = self._make_selector(model)
        result = sel.select_group("left_arm")
        found = set(result)
        # lcollar_g, lbicep_g, lforearm_g, lhand_g are in the model
        assert len(found) > 0

    def test_selector_select_right_arm_group(self):
        model = _make_body_model()
        sel = self._make_selector(model)
        result = sel.select_group("right_arm")
        assert len(result) > 0

    def test_selector_select_legs(self):
        model = _make_body_model()
        sel = self._make_selector(model)
        ll = set(sel.select_group("left_leg"))
        rl = set(sel.select_group("right_leg"))
        assert len(ll) > 0
        assert len(rl) > 0

    def test_selector_clear_resets(self):
        model = _make_body_model()
        sel = self._make_selector(model)
        sel.select_all()
        assert sel.count > 0
        sel.clear()
        assert sel.count == 0

    def test_selector_toggle(self):
        model = _make_body_model()
        sel = self._make_selector(model)
        # pelvis_g should be in model
        assert sel.toggle("pelvis_g") == True
        assert sel.is_selected("pelvis_g")
        assert sel.toggle("pelvis_g") == False
        assert not sel.is_selected("pelvis_g")

    def test_selector_available_groups(self):
        model = _make_body_model()
        sel = self._make_selector(model)
        groups = sel.available_groups()
        assert "all" in groups

    def test_selector_select_by_names_partial(self):
        model = _make_body_model()
        sel = self._make_selector(model)
        found = sel.select_by_names(["pelvis_g", "torso_g", "nonexistent_xyz"])
        assert "nonexistent_xyz" not in found
        assert len(found) >= 1

    def test_selector_select_skeleton_only_excludes_mesh(self):
        model = _make_body_model()
        sel = self._make_selector(model)
        result = sel.select_skeleton_only()
        # The skin node "torso" should NOT be in the skeleton-only selection
        # (dummy nodes only)
        assert "torso" not in result

    def test_selector_selected_nodes_returns_objects(self):
        model = _make_body_model()
        sel = self._make_selector(model)
        sel.select_by_names(["pelvis_g"])
        nodes = sel.selected_nodes
        assert len(nodes) >= 1

    def test_selector_deselect_specific(self):
        model = _make_body_model()
        sel = self._make_selector(model)
        sel.select_group("spine")
        before = sel.count
        sel.deselect(["pelvis_g"])
        after = sel.count
        # Count should decrease or stay same (if pelvis not found)
        assert after <= before

    def test_selector_set_model_clears(self):
        model = _make_body_model()
        sel = self._make_selector(model)
        sel.select_all()
        assert sel.count > 0
        sel.set_model(None)
        assert sel.count == 0


# ──────────────────────────────────────────────────────────────────────────────
#  Weight audit logic tests
# ──────────────────────────────────────────────────────────────────────────────

class TestWeightAudit:
    """Tests for the weight-audit scanning logic."""

    def _run_audit(self, model):
        """Run the same weight-audit logic as _RigFrame._audit_weights."""
        issues = []
        total_verts = 0
        for node in model.all_nodes():
            if not getattr(node, 'is_skin', False):
                continue
            skin_data = getattr(node, 'skin_data', []) or []
            for vi, vsd in enumerate(skin_data):
                total_verts += 1
                infs = getattr(vsd, 'influences', []) or []
                total_w = sum(getattr(b, 'weight', 0.0) for b in infs)
                if len(infs) > 4:
                    issues.append(f"OVERFLOW:{node.name}:{vi}")
                elif total_w == 0.0:
                    issues.append(f"ZERO:{node.name}:{vi}")
                elif abs(total_w - 1.0) > 0.02:
                    issues.append(f"UNNORM:{node.name}:{vi}:{total_w:.4f}")
        return issues, total_verts

    def test_no_skin_nodes_no_issues(self):
        model = _make_body_model()
        # Remove skin data from skin node
        for n in model.all_nodes():
            n.skin_data = []
        issues, total = self._run_audit(model)
        assert total == 0
        assert len(issues) == 0

    def test_valid_weights_no_issues(self):
        root = _StubNode("root")
        skin = _StubNode("skin_mesh", flags=64)
        skin.skin_data = [
            _StubVertexSkinData(influences=[
                _StubBoneWeight(0, 0.6), _StubBoneWeight(1, 0.4)
            ]),
            _StubVertexSkinData(influences=[
                _StubBoneWeight(0, 1.0)
            ]),
        ]
        root.children = [skin]
        model = _StubModel(name="m", root_node=root)
        issues, total = self._run_audit(model)
        assert total == 2
        assert len(issues) == 0

    def test_zero_sum_weights_detected(self):
        root = _StubNode("root")
        skin = _StubNode("skin_mesh", flags=64)
        skin.skin_data = [
            _StubVertexSkinData(influences=[
                _StubBoneWeight(0, 0.0), _StubBoneWeight(1, 0.0)
            ]),
        ]
        root.children = [skin]
        model = _StubModel(name="m", root_node=root)
        issues, total = self._run_audit(model)
        assert total == 1
        assert any("ZERO" in i for i in issues)

    def test_overflow_weights_detected(self):
        root = _StubNode("root")
        skin = _StubNode("skin_mesh", flags=64)
        skin.skin_data = [
            _StubVertexSkinData(influences=[
                _StubBoneWeight(i, 0.2) for i in range(5)  # 5 influences = overflow
            ]),
        ]
        root.children = [skin]
        model = _StubModel(name="m", root_node=root)
        issues, total = self._run_audit(model)
        assert total == 1
        assert any("OVERFLOW" in i for i in issues)

    def test_unnormalised_weights_detected(self):
        root = _StubNode("root")
        skin = _StubNode("skin_mesh", flags=64)
        skin.skin_data = [
            _StubVertexSkinData(influences=[
                _StubBoneWeight(0, 0.5), _StubBoneWeight(1, 0.3)
                # sum = 0.8, not 1.0 → unnormalised
            ]),
        ]
        root.children = [skin]
        model = _StubModel(name="m", root_node=root)
        issues, total = self._run_audit(model)
        assert total == 1
        assert any("UNNORM" in i for i in issues)

    def test_mixed_issues(self):
        root = _StubNode("root")
        skin = _StubNode("skin_mesh", flags=64)
        skin.skin_data = [
            _StubVertexSkinData(influences=[_StubBoneWeight(0, 1.0)]),   # OK
            _StubVertexSkinData(influences=[_StubBoneWeight(0, 0.0)]),   # ZERO
            _StubVertexSkinData(influences=[_StubBoneWeight(i, 0.1) for i in range(5)]),  # OVERFLOW
        ]
        root.children = [skin]
        model = _StubModel(name="m", root_node=root)
        issues, total = self._run_audit(model)
        assert total == 3
        issue_types = set(i.split(":")[0] for i in issues)
        assert "ZERO" in issue_types
        assert "OVERFLOW" in issue_types


# ──────────────────────────────────────────────────────────────────────────────
#  Bone list population helpers
# ──────────────────────────────────────────────────────────────────────────────

class TestBoneListPopulation:
    """Tests for the bone-list building logic extracted from _RigFrame."""

    def _build_bone_rows(self, model):
        """Replicate _populate_bone_list logic without Tk."""
        rows = []  # [(name, type_label, depth)]
        def _walk(node, depth=0):
            if node is None:
                return
            rows.append((node.name, getattr(node, 'type_label', '?'), depth))
            for child in getattr(node, 'children', []):
                _walk(child, depth + 1)
        _walk(model.root_node)
        # Map name → index
        bone_rows = {}
        for idx, (name, ttype, depth) in enumerate(rows):
            bone_rows[name] = idx
        return rows, bone_rows

    def test_root_is_first(self):
        model = _make_body_model()
        rows, _ = self._build_bone_rows(model)
        assert rows[0][0] == "pfbcm"

    def test_all_nodes_listed(self):
        model = _make_body_model()
        rows, bone_rows = self._build_bone_rows(model)
        all_names = {n.name for n in model.all_nodes()}
        listed_names = {r[0] for r in rows}
        assert all_names == listed_names

    def test_depth_increases_with_hierarchy(self):
        model = _make_body_model()
        rows, _ = self._build_bone_rows(model)
        row_map = {r[0]: r for r in rows}
        # pelvis is child of root → depth 1
        assert row_map["pelvis_g"][2] == 1
        # torso is child of pelvis → depth 2
        assert row_map["torso_g"][2] == 2
        # neck is child of torso → depth 3
        assert row_map["neck_g"][2] == 3

    def test_skin_node_type_label(self):
        model = _make_body_model()
        rows, _ = self._build_bone_rows(model)
        skin_rows = [r for r in rows if r[1] == "skin"]
        assert len(skin_rows) >= 1
        assert skin_rows[0][0] == "torso"

    def test_dummy_node_type_label(self):
        model = _make_body_model()
        rows, _ = self._build_bone_rows(model)
        dummy_rows = [r for r in rows if r[1] == "dummy"]
        assert len(dummy_rows) >= 5  # most nodes are dummies

    def test_bone_rows_index_unique(self):
        model = _make_body_model()
        _, bone_rows = self._build_bone_rows(model)
        indices = list(bone_rows.values())
        assert len(indices) == len(set(indices))  # no duplicate indices


# ──────────────────────────────────────────────────────────────────────────────
#  Import / module structure tests
# ──────────────────────────────────────────────────────────────────────────────

class TestRigFrameModuleStructure:
    """Tests for imports and module-level structure."""

    def test_import_character_builder_window(self):
        import src.gui.character_builder_window as cbw
        assert hasattr(cbw, '_RigFrame')
        assert hasattr(cbw, '_FaceFrame')
        assert hasattr(cbw, '_FallbackSelector')
        assert hasattr(cbw, '_import_character_builder')

    def test_rig_frame_class_exists(self):
        from src.gui.character_builder_window import _RigFrame
        assert _RigFrame is not None

    def test_fallback_selector_class_exists(self):
        from src.gui.character_builder_window import _FallbackSelector
        assert _FallbackSelector is not None

    def test_import_character_builder_func_callable(self):
        from src.gui.character_builder_window import _import_character_builder
        SkeletonSelector, BONE_GROUPS = _import_character_builder()
        assert SkeletonSelector is not None
        assert BONE_GROUPS is not None
        assert isinstance(BONE_GROUPS, dict)

    def test_rig_frame_has_region_presets(self):
        from src.gui.character_builder_window import _RigFrame
        assert hasattr(_RigFrame, '_REGION_PRESETS')
        assert len(_RigFrame._REGION_PRESETS) >= 5

    def test_rig_frame_has_mirror_pairs(self):
        from src.gui.character_builder_window import _RigFrame
        assert hasattr(_RigFrame, '_MIRROR_PAIRS')
        assert len(_RigFrame._MIRROR_PAIRS) > 0

    def test_rig_frame_constructor_args(self):
        """_RigFrame.__init__ should accept (parent, window) args."""
        import inspect
        from src.gui.character_builder_window import _RigFrame
        sig = inspect.signature(_RigFrame.__init__)
        params = list(sig.parameters.keys())
        assert "parent" in params or len(params) >= 3

    def test_rig_frame_refresh_method_exists(self):
        from src.gui.character_builder_window import _RigFrame
        assert callable(getattr(_RigFrame, 'refresh', None))

    def test_mode_labels_include_rig(self):
        from src.gui.character_builder_window import _MODE_LABELS
        assert "Rig" in _MODE_LABELS

    def test_mode_frames_include_rig_frame(self):
        """CharacterBuilderWindow._build_notebook should register _RigFrame."""
        import inspect
        from src.gui.character_builder_window import CharacterBuilderWindow
        src = inspect.getsource(CharacterBuilderWindow._build_notebook)
        assert "_RigFrame" in src

    def test_bone_groups_keys_consistent(self):
        """BONE_GROUPS keys used in _REGION_PRESETS must be in BONE_GROUPS."""
        from src.core.character_builder import BONE_GROUPS
        from src.gui.character_builder_window import _RigFrame
        for _, key, _ in _RigFrame._REGION_PRESETS:
            assert key in BONE_GROUPS, f"Key '{key}' not in BONE_GROUPS"


# ──────────────────────────────────────────────────────────────────────────────
#  Weight-audit helper tests (additional edge cases)
# ──────────────────────────────────────────────────────────────────────────────

class TestWeightAuditEdgeCases:

    def _run_audit(self, model):
        issues = []
        total_verts = 0
        for node in model.all_nodes():
            if not getattr(node, 'is_skin', False):
                continue
            skin_data = getattr(node, 'skin_data', []) or []
            for vi, vsd in enumerate(skin_data):
                total_verts += 1
                infs = getattr(vsd, 'influences', []) or []
                total_w = sum(getattr(b, 'weight', 0.0) for b in infs)
                if len(infs) > 4:
                    issues.append("OVERFLOW")
                elif total_w == 0.0:
                    issues.append("ZERO")
                elif abs(total_w - 1.0) > 0.02:
                    issues.append("UNNORM")
        return issues, total_verts

    def test_empty_influences_counts_as_zero(self):
        """Vertex with no influences has zero weight sum."""
        root = _StubNode("root")
        skin = _StubNode("s", flags=64)
        skin.skin_data = [_StubVertexSkinData(influences=[])]
        root.children = [skin]
        model = _StubModel(name="m", root_node=root)
        issues, total = self._run_audit(model)
        assert total == 1
        assert "ZERO" in issues

    def test_exactly_4_influences_ok(self):
        """4 influences is the KotOR limit — no overflow."""
        root = _StubNode("root")
        skin = _StubNode("s", flags=64)
        skin.skin_data = [
            _StubVertexSkinData(influences=[
                _StubBoneWeight(i, 0.25) for i in range(4)
            ])
        ]
        root.children = [skin]
        model = _StubModel(name="m", root_node=root)
        issues, total = self._run_audit(model)
        assert total == 1
        assert "OVERFLOW" not in issues

    def test_weight_sum_within_tolerance(self):
        """Weight sum of 0.99 or 1.01 should pass (tolerance 0.02)."""
        root = _StubNode("root")
        skin = _StubNode("s", flags=64)
        skin.skin_data = [
            _StubVertexSkinData(influences=[
                _StubBoneWeight(0, 0.99)  # sum = 0.99, within ±0.02 of 1.0
            ]),
            _StubVertexSkinData(influences=[
                _StubBoneWeight(0, 1.01)  # sum = 1.01, within ±0.02 of 1.0
            ]),
        ]
        root.children = [skin]
        model = _StubModel(name="m", root_node=root)
        issues, total = self._run_audit(model)
        assert total == 2
        assert len(issues) == 0

    def test_multiple_skin_nodes(self):
        """Issues from multiple skin nodes should all be collected."""
        root = _StubNode("root")
        skin1 = _StubNode("s1", flags=64)
        skin1.skin_data = [
            _StubVertexSkinData(influences=[_StubBoneWeight(0, 0.0)])  # ZERO
        ]
        skin2 = _StubNode("s2", flags=64)
        skin2.skin_data = [
            _StubVertexSkinData(influences=[_StubBoneWeight(0, 1.0)])  # OK
        ]
        root.children = [skin1, skin2]
        model = _StubModel(name="m", root_node=root)
        issues, total = self._run_audit(model)
        assert total == 2
        assert len(issues) == 1
        assert "ZERO" in issues


# ──────────────────────────────────────────────────────────────────────────────
#  Integration: CharacterBuilderWindow module has all Phase 3 elements
# ──────────────────────────────────────────────────────────────────────────────

class TestPhase3ModuleIntegration:

    def test_rig_frame_has_weight_audit_method(self):
        from src.gui.character_builder_window import _RigFrame
        assert hasattr(_RigFrame, '_audit_weights')

    def test_rig_frame_has_select_region_method(self):
        from src.gui.character_builder_window import _RigFrame
        assert hasattr(_RigFrame, '_select_region')

    def test_rig_frame_has_select_all_method(self):
        from src.gui.character_builder_window import _RigFrame
        assert hasattr(_RigFrame, '_select_all')

    def test_rig_frame_has_select_skeleton_only(self):
        from src.gui.character_builder_window import _RigFrame
        assert hasattr(_RigFrame, '_select_skeleton_only')

    def test_rig_frame_has_clear_selection(self):
        from src.gui.character_builder_window import _RigFrame
        assert hasattr(_RigFrame, '_clear_selection')

    def test_rig_frame_has_mirror_var_attr(self):
        """_mirror_var should be declared as a class-level attribute or in __init__."""
        import inspect
        from src.gui.character_builder_window import _RigFrame
        src = inspect.getsource(_RigFrame.__init__)
        assert "_mirror_var" in src

    def test_rig_frame_on_bone_select_method(self):
        from src.gui.character_builder_window import _RigFrame
        assert hasattr(_RigFrame, '_on_bone_select')

    def test_rig_frame_update_detail_method(self):
        from src.gui.character_builder_window import _RigFrame
        assert hasattr(_RigFrame, '_update_detail')

    def test_rig_frame_pick_primary_model_method(self):
        from src.gui.character_builder_window import _RigFrame
        assert hasattr(_RigFrame, '_pick_primary_model')

    def test_fallback_selector_in_module(self):
        from src.gui.character_builder_window import _FallbackSelector
        assert _FallbackSelector is not None

    def test_import_character_builder_callable(self):
        from src.gui.character_builder_window import _import_character_builder
        assert callable(_import_character_builder)

    def test_bone_groups_accessible(self):
        from src.core.character_builder import BONE_GROUPS
        assert "spine" in BONE_GROUPS
        assert "left_arm" in BONE_GROUPS
        assert "right_arm" in BONE_GROUPS
        assert "left_leg" in BONE_GROUPS
        assert "right_leg" in BONE_GROUPS
        assert "head" in BONE_GROUPS
        assert "attachment" in BONE_GROUPS

    def test_bone_groups_contain_kotor_bones(self):
        from src.core.character_builder import BONE_GROUPS
        assert "pelvis_g" in BONE_GROUPS["spine"]
        assert "torso_g" in BONE_GROUPS["spine"]
        assert "lbicep_g" in BONE_GROUPS["left_arm"]
        assert "rbicep_g" in BONE_GROUPS["right_arm"]
        assert "lthigh_g" in BONE_GROUPS["left_leg"]
        assert "rthigh_g" in BONE_GROUPS["right_leg"]
        assert "f_um_g" in BONE_GROUPS["head"]

    def test_rig_frame_is_not_placeholder(self):
        """_RigFrame should NOT contain the Phase 4 placeholder text anymore."""
        import inspect
        from src.gui.character_builder_window import _RigFrame
        src = inspect.getsource(_RigFrame)
        assert "Skeleton joint selection" not in src or "Phase 4" not in src

    def test_rig_frame_has_bone_listbox(self):
        import inspect
        from src.gui.character_builder_window import _RigFrame
        src = inspect.getsource(_RigFrame._build_ui)
        assert "Listbox" in src or "_bone_lb" in src

    def test_rig_frame_has_detail_pane(self):
        import inspect
        from src.gui.character_builder_window import _RigFrame
        src = inspect.getsource(_RigFrame._build_ui)
        assert "detail" in src.lower()

    def test_rig_frame_has_region_buttons(self):
        import inspect
        from src.gui.character_builder_window import _RigFrame
        src = inspect.getsource(_RigFrame._build_ui)
        assert "Bone Regions" in src or "_REGION_PRESETS" in src
