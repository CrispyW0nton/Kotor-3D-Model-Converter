"""
test_v410_face_mode.py
=======================
Comprehensive tests for Phase 3 of the GhostRigger Character Builder:
  Face Mode (_FaceFrame) — facial-bone checklist, hook-alignment table,
  talk-animation list, lip-sync preview wiring.

Tests are fully headless (no Tk display required).

Coverage:
  • _FaceFrame class structure and required attributes
  • Facial bone definitions (_FACIAL_BONES) correctness
  • Hook node definitions (_HOOK_NODES) completeness
  • Talk animation definitions (_TALK_ANIMS)
  • _FaceFrame._pick_head_model() slot priority (HEAD_SHELL preferred)
  • Bone checklist logic (present/missing/required)
  • Hook alignment table output logic
  • Talk animation discovery logic
  • Lip-sync play/stop method signatures
  • Module-level integration: Face mode registered in CharacterBuilderWindow
"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


# ──────────────────────────────────────────────────────────────────────────────
#  Minimal model stubs (reused pattern from test_v400)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class _StubAnim:
    name: str = ""
    length: float = 1.0

@dataclass
class _StubNode:
    name: str
    flags: int = 0x01
    position: tuple = (0.0, 0.0, 0.0)
    children: List["_StubNode"] = field(default_factory=list)
    parent: Optional["_StubNode"] = None

    @property
    def type_label(self):
        return "dummy"

    def bone_world_position(self):
        return self.position


@dataclass
class _StubModel:
    name: str = "test_model"
    root_node: Optional[_StubNode] = None
    animations: List[_StubAnim] = field(default_factory=list)
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


def _make_complete_head_model():
    """A head model with all required facial bones and hooks."""
    root    = _StubNode("pfhc01")
    neck    = _StubNode("neck_g",       position=(0.0, 0.0, 1.45))
    necklwr = _StubNode("necklwr_g",    position=(0.0, 0.0, 1.48))
    headg   = _StubNode("head_g",       position=(0.0, 0.0, 1.60))
    f_um    = _StubNode("f_um_g",       position=(0.0, -0.05, 1.62))
    f_jaw   = _StubNode("f_jaw_g",      position=(0.0, -0.04, 1.55))
    f_lmc   = _StubNode("f_lmc_g",      position=(0.05, -0.04, 1.60))
    f_rmc   = _StubNode("f_rmc_g",      position=(-0.05, -0.04, 1.60))
    f_Llm   = _StubNode("f_Llm_g",      position=(0.04, -0.04, 1.57))
    f_Rlm   = _StubNode("f_Rlm_g",      position=(-0.04, -0.04, 1.57))
    f_tt    = _StubNode("f_tonguetip_g", position=(0.0, -0.06, 1.56))
    f_lbrw  = _StubNode("f_lbrw_g",     position=(0.04, 0.0, 1.67))
    f_rbrw  = _StubNode("f_rbrw_g",     position=(-0.04, 0.0, 1.67))
    f_mbrw  = _StubNode("f_mdbrw_g",    position=(0.0, 0.0, 1.67))
    eyeLlid = _StubNode("eyeLlid",      position=(0.035, 0.04, 1.63))
    eyeRlid = _StubNode("eyeRlid",      position=(-0.035, 0.04, 1.63))
    eyeLA   = _StubNode("eyeLA",        position=(0.04, 0.05, 1.62))
    eyeRA   = _StubNode("eyeRA",        position=(-0.04, 0.05, 1.62))
    tl      = _StubNode("teethlower",   position=(0.0, -0.05, 1.57))
    tu      = _StubNode("teethupper",   position=(0.0, -0.05, 1.59))
    # Hooks
    talk    = _StubNode("talkdummy",    position=(0.0, 0.0, 1.65))
    headhk  = _StubNode("headhook",     position=(0.0, 0.0, 1.70))
    camhk   = _StubNode("camerahook",   position=(0.0, 0.2, 1.65))
    cscene  = _StubNode("cutscenedummy",position=(0.0, 0.0, 1.65))
    mask    = _StubNode("MaskHook",     position=(0.0, 0.0, 1.68))
    goggle  = _StubNode("GoggleHook",   position=(0.0, 0.0, 1.67))

    root.children = [neck]
    neck.children = [necklwr]
    necklwr.children = [headg]
    headg.children = [
        f_um, f_jaw, f_lmc, f_rmc, f_Llm, f_Rlm, f_tt,
        f_lbrw, f_rbrw, f_mbrw,
        eyeLlid, eyeRlid, eyeLA, eyeRA, tl, tu,
        talk, headhk, camhk, cscene, mask, goggle,
    ]

    # Talk animations
    anims = [
        _StubAnim("tlknorm"),
        _StubAnim("tlklaff"),
        _StubAnim("tlkargue"),
        _StubAnim("tlkforce"),
        _StubAnim("walk"),
        _StubAnim("run"),
    ]

    return _StubModel(name="pfhc01", root_node=root, animations=anims)


def _make_minimal_head_model():
    """A head model with only the required facial bones."""
    root   = _StubNode("pfhc01_min")
    neck   = _StubNode("neck_g",   position=(0.0, 0.0, 1.45))
    headg  = _StubNode("head_g",   position=(0.0, 0.0, 1.60))
    f_um   = _StubNode("f_um_g",   position=(0.0, -0.05, 1.62))
    f_jaw  = _StubNode("f_jaw_g",  position=(0.0, -0.04, 1.55))
    f_lmc  = _StubNode("f_lmc_g",  position=(0.05, -0.04, 1.60))
    f_rmc  = _StubNode("f_rmc_g",  position=(-0.05, -0.04, 1.60))
    talk   = _StubNode("talkdummy",position=(0.0, 0.0, 1.65))
    headhk = _StubNode("headhook", position=(0.0, 0.0, 1.70))

    root.children = [neck]
    neck.children = [headg]
    headg.children = [f_um, f_jaw, f_lmc, f_rmc, talk, headhk]

    return _StubModel(name="pfhc01_min", root_node=root)


def _make_body_model():
    """A body stub (for testing head selection priority)."""
    root = _StubNode("pfbcm")
    pelvis = _StubNode("pelvis_g")
    root.children = [pelvis]
    return _StubModel(name="pfbcm", root_node=root)


def _make_scene_with(body=None, head=None, accessory=None):
    from src.core.model_data import CharacterScene, PartSlot
    scene = CharacterScene(game_version="K1")
    if body is not None:
        scene.assign(PartSlot.HEADLESS_BODY, body, resref="pfbcm",
                     game_version="K1", source_path="/tmp/pfbcm.mdl")
    if head is not None:
        scene.assign(PartSlot.HEAD_SHELL, head, resref="pfhc01",
                     game_version="K1", source_path="/tmp/pfhc01.mdl")
    if accessory is not None:
        scene.assign(PartSlot.ACCESSORY, accessory, resref="acc",
                     game_version="K1", source_path="/tmp/acc.mdl")
    return scene


# ──────────────────────────────────────────────────────────────────────────────
#  Module structure tests
# ──────────────────────────────────────────────────────────────────────────────

class TestFaceModeModuleStructure:

    def test_face_frame_class_exists(self):
        from src.gui.character_builder_window import _FaceFrame
        assert _FaceFrame is not None

    def test_face_frame_has_facial_bones(self):
        from src.gui.character_builder_window import _FaceFrame
        assert hasattr(_FaceFrame, '_FACIAL_BONES')
        assert isinstance(_FaceFrame._FACIAL_BONES, list)
        assert len(_FaceFrame._FACIAL_BONES) >= 10

    def test_face_frame_has_hook_nodes(self):
        from src.gui.character_builder_window import _FaceFrame
        assert hasattr(_FaceFrame, '_HOOK_NODES')
        assert isinstance(_FaceFrame._HOOK_NODES, list)
        assert len(_FaceFrame._HOOK_NODES) >= 4

    def test_face_frame_has_talk_anims(self):
        from src.gui.character_builder_window import _FaceFrame
        assert hasattr(_FaceFrame, '_TALK_ANIMS')
        assert isinstance(_FaceFrame._TALK_ANIMS, list)
        assert len(_FaceFrame._TALK_ANIMS) >= 3

    def test_face_frame_has_refresh_method(self):
        from src.gui.character_builder_window import _FaceFrame
        assert callable(getattr(_FaceFrame, 'refresh', None))

    def test_face_frame_has_pick_head_model(self):
        from src.gui.character_builder_window import _FaceFrame
        assert hasattr(_FaceFrame, '_pick_head_model')

    def test_face_frame_has_update_bone_checklist(self):
        from src.gui.character_builder_window import _FaceFrame
        assert hasattr(_FaceFrame, '_update_bone_checklist')

    def test_face_frame_has_update_hook_table(self):
        from src.gui.character_builder_window import _FaceFrame
        assert hasattr(_FaceFrame, '_update_hook_table')

    def test_face_frame_has_update_anim_list(self):
        from src.gui.character_builder_window import _FaceFrame
        assert hasattr(_FaceFrame, '_update_anim_list')

    def test_face_frame_has_play_anim(self):
        from src.gui.character_builder_window import _FaceFrame
        assert hasattr(_FaceFrame, '_play_selected_anim')

    def test_face_frame_has_stop_anim(self):
        from src.gui.character_builder_window import _FaceFrame
        assert hasattr(_FaceFrame, '_stop_anim')

    def test_face_frame_has_reset_to_empty(self):
        from src.gui.character_builder_window import _FaceFrame
        assert hasattr(_FaceFrame, '_reset_to_empty')

    def test_mode_labels_include_face(self):
        from src.gui.character_builder_window import _MODE_LABELS
        assert "Face" in _MODE_LABELS

    def test_face_mode_index_correct(self):
        from src.gui.character_builder_window import _MODE_LABELS
        assert _MODE_LABELS.index("Face") == 2

    def test_face_frame_registered_in_notebook(self):
        import inspect
        from src.gui.character_builder_window import CharacterBuilderWindow
        src = inspect.getsource(CharacterBuilderWindow._build_notebook)
        assert "_FaceFrame" in src

    def test_face_frame_not_placeholder(self):
        """_FaceFrame should NOT still contain the Phase 5 placeholder text."""
        import inspect
        from src.gui.character_builder_window import _FaceFrame
        src = inspect.getsource(_FaceFrame)
        # Original placeholder: "will be implemented in Phase 5"
        assert "will be implemented in Phase 5" not in src


# ──────────────────────────────────────────────────────────────────────────────
#  Facial bone definitions
# ──────────────────────────────────────────────────────────────────────────────

class TestFacialBoneDefinitions:

    def _get_bones(self):
        from src.gui.character_builder_window import _FaceFrame
        return _FaceFrame._FACIAL_BONES

    def test_facial_bones_tuple_format(self):
        for bone in self._get_bones():
            assert len(bone) == 3, f"Bone entry should have 3 elements: {bone}"
            display, node_names, required = bone
            assert isinstance(display, str) and display
            assert isinstance(node_names, list) and len(node_names) >= 1
            assert isinstance(required, bool)

    def test_required_facial_bones_present(self):
        bones = self._get_bones()
        required_nodes = {
            nn
            for _, nns, req in bones
            for nn in nns
            if req
        }
        # KotOR canonical required facial bones
        assert "f_um_g"  in required_nodes or any("f_um_g" in nns for _, nns, req in bones if req)
        assert "f_jaw_g" in required_nodes or any("f_jaw_g" in nns for _, nns, req in bones if req)
        assert "f_lmc_g" in required_nodes or any("f_lmc_g" in nns for _, nns, req in bones if req)
        assert "f_rmc_g" in required_nodes or any("f_rmc_g" in nns for _, nns, req in bones if req)

    def test_head_bone_in_list(self):
        bones = self._get_bones()
        all_node_names = [nn for _, nns, _ in bones for nn in nns]
        assert "head_g" in all_node_names

    def test_neck_bone_in_list(self):
        bones = self._get_bones()
        all_node_names = [nn for _, nns, _ in bones for nn in nns]
        assert "neck_g" in all_node_names

    def test_eyelid_bones_in_list(self):
        bones = self._get_bones()
        all_node_names = [nn for _, nns, _ in bones for nn in nns]
        assert "eyeLlid" in all_node_names
        assert "eyeRlid" in all_node_names

    def test_no_duplicate_primary_names(self):
        bones = self._get_bones()
        primaries = [nns[0] for _, nns, _ in bones]
        assert len(primaries) == len(set(primaries)), "Duplicate primary bone names"

    def test_teeth_nodes_in_list(self):
        bones = self._get_bones()
        all_node_names = [nn for _, nns, _ in bones for nn in nns]
        assert "teethlower" in all_node_names or "teethupper" in all_node_names

    def test_display_names_non_empty(self):
        for display, _, _ in self._get_bones():
            assert len(display.strip()) > 0


# ──────────────────────────────────────────────────────────────────────────────
#  Hook node definitions
# ──────────────────────────────────────────────────────────────────────────────

class TestHookNodeDefinitions:

    def _get_hooks(self):
        from src.gui.character_builder_window import _FaceFrame
        return _FaceFrame._HOOK_NODES

    def test_hook_nodes_tuple_format(self):
        for hook in self._get_hooks():
            assert len(hook) == 3
            display, node_name, required = hook
            assert isinstance(display, str) and display
            assert isinstance(node_name, str) and node_name
            assert isinstance(required, bool)

    def test_talkdummy_is_required(self):
        hooks = self._get_hooks()
        found = [(d, n, r) for d, n, r in hooks if n == "talkdummy"]
        assert len(found) >= 1
        assert found[0][2] == True  # required

    def test_headhook_is_required(self):
        hooks = self._get_hooks()
        found = [(d, n, r) for d, n, r in hooks if n == "headhook"]
        assert len(found) >= 1
        assert found[0][2] == True

    def test_camerahook_optional(self):
        hooks = self._get_hooks()
        found = [(d, n, r) for d, n, r in hooks if n == "camerahook"]
        if found:
            # camerahook is optional
            assert found[0][2] == False

    def test_required_hooks_at_least_two(self):
        hooks = self._get_hooks()
        required = [h for h in hooks if h[2]]
        assert len(required) >= 2

    def test_no_duplicate_hook_names(self):
        hooks = self._get_hooks()
        names = [n for _, n, _ in hooks]
        assert len(names) == len(set(names))


# ──────────────────────────────────────────────────────────────────────────────
#  Talk animation definitions
# ──────────────────────────────────────────────────────────────────────────────

class TestTalkAnimDefinitions:

    def _get_anims(self):
        from src.gui.character_builder_window import _FaceFrame
        return _FaceFrame._TALK_ANIMS

    def test_talk_anims_tuple_format(self):
        for anim in self._get_anims():
            assert len(anim) == 2
            label, prefix = anim
            assert isinstance(label, str) and label
            assert isinstance(prefix, str) and prefix

    def test_tlknorm_present(self):
        anims = self._get_anims()
        prefixes = [p for _, p in anims]
        assert "tlknorm" in prefixes

    def test_tlklaff_present(self):
        anims = self._get_anims()
        prefixes = [p for _, p in anims]
        assert "tlklaff" in prefixes

    def test_tlkargue_present(self):
        anims = self._get_anims()
        prefixes = [p for _, p in anims]
        assert "tlkargue" in prefixes

    def test_no_empty_prefixes(self):
        for _, prefix in self._get_anims():
            assert prefix.strip() != ""

    def test_labels_non_empty(self):
        for label, _ in self._get_anims():
            assert label.strip() != ""


# ──────────────────────────────────────────────────────────────────────────────
#  _pick_head_model slot priority
# ──────────────────────────────────────────────────────────────────────────────

class _MockWindow:
    def __init__(self, scene):
        self.scene = scene
        self._mode_frames = [None] * 5


class _MockFaceFrame:
    """Minimal face frame without Tk for testing _pick_head_model."""
    def __init__(self, scene):
        self._win = _MockWindow(scene)

    def _pick_head_model(self):
        from src.gui.character_builder_window import _import_model_data
        try:
            PartSlot = _import_model_data()[1]
            scene = self._win.scene
            entry = scene.slots.get(PartSlot.HEAD_SHELL)
            if entry and entry.model is not None:
                return entry.model
            for entry in scene.slots.values():
                if entry.model is not None:
                    return entry.model
        except Exception:
            pass
        return None


class TestFaceFrameModelSelection:

    def test_empty_scene_returns_none(self):
        from src.core.model_data import CharacterScene
        scene = CharacterScene(game_version="K1")
        frame = _MockFaceFrame(scene)
        assert frame._pick_head_model() is None

    def test_head_shell_preferred_over_body(self):
        body = _make_body_model()
        head = _make_complete_head_model()
        scene = _make_scene_with(body=body, head=head)
        frame = _MockFaceFrame(scene)
        result = frame._pick_head_model()
        # HEAD_SHELL takes priority for face mode
        assert result is head

    def test_body_used_as_fallback_when_no_head(self):
        body = _make_body_model()
        scene = _make_scene_with(body=body)
        frame = _MockFaceFrame(scene)
        result = frame._pick_head_model()
        # No head → fall back to body
        assert result is body

    def test_accessory_used_when_only_slot(self):
        from src.core.model_data import CharacterScene, PartSlot
        acc = _make_body_model()
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.ACCESSORY, acc, resref="acc",
                     game_version="K1", source_path="/tmp/acc.mdl")
        frame = _MockFaceFrame(scene)
        result = frame._pick_head_model()
        assert result is acc

    def test_head_preferred_over_accessory(self):
        from src.core.model_data import CharacterScene, PartSlot
        head = _make_complete_head_model()
        acc  = _make_body_model()
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEAD_SHELL, head, resref="pfhc01",
                     game_version="K1", source_path="/tmp/pfhc01.mdl")
        scene.assign(PartSlot.ACCESSORY, acc, resref="acc",
                     game_version="K1", source_path="/tmp/acc.mdl")
        frame = _MockFaceFrame(scene)
        result = frame._pick_head_model()
        assert result is head


# ──────────────────────────────────────────────────────────────────────────────
#  Bone checklist logic
# ──────────────────────────────────────────────────────────────────────────────

class TestBoneChecklistLogic:
    """Tests for the facial-bone presence/absence detection logic."""

    def _check_bones(self, model):
        """Replicate _update_bone_checklist logic without Tk."""
        from src.gui.character_builder_window import _FaceFrame
        try:
            node_names_lower = {n.name.lower() for n in model.all_nodes()}
        except Exception:
            node_names_lower = set()

        results = {}  # primary_name → (found, required)
        for display_name, node_names, required in _FaceFrame._FACIAL_BONES:
            primary_name = node_names[0]
            found = any(nn.lower() in node_names_lower for nn in node_names)
            results[primary_name] = (found, required)
        return results

    def test_complete_head_all_required_found(self):
        model = _make_complete_head_model()
        results = self._check_bones(model)
        # All required bones should be found
        for name, (found, required) in results.items():
            if required:
                assert found, f"Required bone not found: {name}"

    def test_minimal_head_required_found(self):
        model = _make_minimal_head_model()
        results = self._check_bones(model)
        required_results = {k: v for k, v in results.items() if v[1]}
        for name, (found, _) in required_results.items():
            assert found, f"Required bone not found in minimal head: {name}"

    def test_empty_model_all_missing(self):
        root = _StubNode("empty_root")
        model = _StubModel(name="empty", root_node=root)
        results = self._check_bones(model)
        for name, (found, _) in results.items():
            assert not found, f"Should not find {name} in empty model"

    def test_partial_head_optional_missing(self):
        model = _make_minimal_head_model()
        results = self._check_bones(model)
        optional_results = {k: v for k, v in results.items() if not v[1]}
        # Most optional bones should be missing in minimal head
        missing_count = sum(1 for found, _ in optional_results.values() if not found)
        assert missing_count >= 5, f"Expected many optional bones missing, got {missing_count}"

    def test_head_g_found_in_complete_model(self):
        model = _make_complete_head_model()
        results = self._check_bones(model)
        assert results.get("head_g", (False, False))[0] == True

    def test_eyeLlid_found_in_complete_model(self):
        model = _make_complete_head_model()
        results = self._check_bones(model)
        assert results.get("eyeLlid", (False, False))[0] == True

    def test_f_um_g_found_in_complete_model(self):
        model = _make_complete_head_model()
        results = self._check_bones(model)
        assert results.get("f_um_g", (False, False))[0] == True

    def test_f_jaw_g_found_in_complete_model(self):
        model = _make_complete_head_model()
        results = self._check_bones(model)
        assert results.get("f_jaw_g", (False, False))[0] == True

    def test_case_insensitive_match(self):
        """Bone matching should be case-insensitive."""
        root = _StubNode("root")
        # Upper-case variant
        headg = _StubNode("Head_G")   # should match "head_g" case-insensitively
        neck  = _StubNode("NECK_G")
        f_um  = _StubNode("F_UM_G")
        f_jaw = _StubNode("F_JAW_G")
        f_lmc = _StubNode("F_LMC_G")
        f_rmc = _StubNode("F_RMC_G")
        talk  = _StubNode("TalkDummy")
        headhk= _StubNode("HeadHook")
        root.children = [neck, headg, f_um, f_jaw, f_lmc, f_rmc, talk, headhk]
        model = _StubModel(name="caseless", root_node=root)
        results = self._check_bones(model)
        assert results.get("head_g", (False, False))[0] == True
        assert results.get("neck_g", (False, False))[0] == True


# ──────────────────────────────────────────────────────────────────────────────
#  Hook alignment table logic
# ──────────────────────────────────────────────────────────────────────────────

class TestHookAlignmentLogic:
    """Tests for hook node detection and position reporting."""

    def _get_hook_status(self, model):
        """Replicate hook detection logic without Tk."""
        from src.gui.character_builder_window import _FaceFrame
        node_map = {}
        try:
            for n in model.all_nodes():
                node_map[n.name.lower()] = n
        except Exception:
            pass

        results = {}
        for display_name, node_name, required in _FaceFrame._HOOK_NODES:
            node = node_map.get(node_name.lower())
            if node is None:
                results[node_name] = {"found": False, "required": required,
                                      "pos": None}
            else:
                try:
                    pos = node.bone_world_position()
                except Exception:
                    pos = getattr(node, 'position', (0, 0, 0))
                results[node_name] = {"found": True, "required": required,
                                      "pos": pos}
        return results

    def test_complete_head_all_hooks_found(self):
        model = _make_complete_head_model()
        results = self._get_hook_status(model)
        for node_name, info in results.items():
            if info["required"]:
                assert info["found"], f"Required hook not found: {node_name}"

    def test_minimal_head_required_hooks_found(self):
        model = _make_minimal_head_model()
        results = self._get_hook_status(model)
        required = {k: v for k, v in results.items() if v["required"]}
        for name, info in required.items():
            assert info["found"], f"Required hook {name} missing from minimal head"

    def test_empty_model_hooks_missing(self):
        root = _StubNode("root")
        model = _StubModel(name="empty", root_node=root)
        results = self._get_hook_status(model)
        required = [v for v in results.values() if v["required"]]
        missing_required = [v for v in required if not v["found"]]
        assert len(missing_required) >= 2  # talkdummy and headhook

    def test_hook_position_returned(self):
        model = _make_complete_head_model()
        results = self._get_hook_status(model)
        talkdummy = results.get("talkdummy")
        assert talkdummy is not None
        assert talkdummy["found"] == True
        assert talkdummy["pos"] is not None
        pos = talkdummy["pos"]
        assert len(pos) == 3

    def test_camera_hook_position_reasonable(self):
        model = _make_complete_head_model()
        results = self._get_hook_status(model)
        camhook = results.get("camerahook")
        if camhook and camhook["found"]:
            pos = camhook["pos"]
            # Camera hook should be above the ground (z > 1.0 for a standing character)
            assert pos[2] > 1.0

    def test_headhook_above_talkdummy(self):
        """headhook is typically above talkdummy in Z axis."""
        model = _make_complete_head_model()
        results = self._get_hook_status(model)
        hh = results.get("headhook")
        td = results.get("talkdummy")
        if hh and td and hh["found"] and td["found"]:
            assert hh["pos"][2] >= td["pos"][2] - 0.01

    def test_find_attachment_nodes(self):
        """Other nodes with 'hook', 'dummy', 'conjure', 'impact' should be found."""
        model = _make_complete_head_model()
        node_names_lower = {n.name.lower() for n in model.all_nodes()}
        attachment_kws = ("hook", "dummy", "conjure", "impact")
        found = [n for n in node_names_lower
                 if any(kw in n for kw in attachment_kws)]
        assert len(found) >= 2  # at minimum talkdummy, headhook


# ──────────────────────────────────────────────────────────────────────────────
#  Talk animation discovery logic
# ──────────────────────────────────────────────────────────────────────────────

class TestTalkAnimDiscovery:
    """Tests for animation list building and talk animation detection."""

    def _find_talk_anims(self, model):
        """Replicate _update_anim_list talk anim detection logic."""
        from src.gui.character_builder_window import _FaceFrame
        anims = getattr(model, 'animations', []) or []
        talk_anims = []
        other_anims = []
        for anim in anims:
            anim_name = getattr(anim, 'name', '') or ''
            is_talk = False
            for _, prefix in _FaceFrame._TALK_ANIMS:
                if prefix.lower() in anim_name.lower():
                    is_talk = True
                    break
            if is_talk:
                talk_anims.append(anim_name)
            else:
                other_anims.append(anim_name)
        return talk_anims, other_anims

    def test_complete_head_talk_anims_found(self):
        model = _make_complete_head_model()
        talk, other = self._find_talk_anims(model)
        assert len(talk) >= 3
        assert "tlknorm" in talk
        assert "tlklaff" in talk
        assert "tlkargue" in talk

    def test_complete_head_other_anims_found(self):
        model = _make_complete_head_model()
        talk, other = self._find_talk_anims(model)
        assert "walk" in other
        assert "run" in other

    def test_no_animations_returns_empty(self):
        model = _make_minimal_head_model()
        model.animations = []
        talk, other = self._find_talk_anims(model)
        assert len(talk) == 0
        assert len(other) == 0

    def test_only_talk_anims_no_other(self):
        model = _make_minimal_head_model()
        model.animations = [
            _StubAnim("tlknorm"), _StubAnim("tlklaff"),
        ]
        talk, other = self._find_talk_anims(model)
        assert len(talk) == 2
        assert len(other) == 0

    def test_mixed_prefix_match(self):
        """Test that prefixes are matched as substrings."""
        model = _make_minimal_head_model()
        model.animations = [
            _StubAnim("tlknorm_idle"),   # contains "tlknorm"
            _StubAnim("other_action"),
        ]
        talk, other = self._find_talk_anims(model)
        assert "tlknorm_idle" in talk
        assert "other_action" in other

    def test_case_insensitive_match(self):
        model = _make_minimal_head_model()
        model.animations = [_StubAnim("TLKNORM")]  # uppercase
        talk, other = self._find_talk_anims(model)
        assert "TLKNORM" in talk

    def test_tlkforce_detected(self):
        model = _make_minimal_head_model()
        model.animations = [_StubAnim("tlkforce")]
        talk, _ = self._find_talk_anims(model)
        assert "tlkforce" in talk


# ──────────────────────────────────────────────────────────────────────────────
#  Play/stop animation method signatures
# ──────────────────────────────────────────────────────────────────────────────

class TestAnimPlayStopSignatures:

    def test_play_method_exists(self):
        import inspect
        from src.gui.character_builder_window import _FaceFrame
        assert callable(_FaceFrame._play_selected_anim)
        sig = inspect.signature(_FaceFrame._play_selected_anim)
        # Should accept self only (no required extra args)
        params = [p for p in sig.parameters if p != 'self']
        assert len(params) == 0

    def test_stop_method_exists(self):
        import inspect
        from src.gui.character_builder_window import _FaceFrame
        assert callable(_FaceFrame._stop_anim)
        sig = inspect.signature(_FaceFrame._stop_anim)
        params = [p for p in sig.parameters if p != 'self']
        assert len(params) == 0

    def test_play_references_preview_frame(self):
        """_play_selected_anim should try to access the Preview tab viewport."""
        import inspect
        from src.gui.character_builder_window import _FaceFrame
        src = inspect.getsource(_FaceFrame._play_selected_anim)
        assert "_mode_frames" in src or "preview_frame" in src or "viewport" in src.lower()

    def test_stop_references_preview_frame(self):
        import inspect
        from src.gui.character_builder_window import _FaceFrame
        src = inspect.getsource(_FaceFrame._stop_anim)
        assert "_mode_frames" in src or "preview_frame" in src or "viewport" in src.lower()


# ──────────────────────────────────────────────────────────────────────────────
#  Face mode UI construction inspection (headless)
# ──────────────────────────────────────────────────────────────────────────────

class TestFaceModeUIConstruction:
    """Non-Tk tests that inspect the _build_ui source code structure."""

    def test_build_ui_has_facial_bone_section(self):
        import inspect
        from src.gui.character_builder_window import _FaceFrame
        src = inspect.getsource(_FaceFrame._build_ui)
        assert "Facial Bones" in src or "_fb_labels" in src

    def test_build_ui_has_hook_alignment_section(self):
        import inspect
        from src.gui.character_builder_window import _FaceFrame
        src = inspect.getsource(_FaceFrame._build_ui)
        assert "Hook Alignment" in src or "_hook_text" in src

    def test_build_ui_has_lip_sync_section(self):
        import inspect
        from src.gui.character_builder_window import _FaceFrame
        src = inspect.getsource(_FaceFrame._build_ui)
        assert "Lip-Sync" in src or "_anim_listbox" in src

    def test_build_ui_has_play_button(self):
        import inspect
        from src.gui.character_builder_window import _FaceFrame
        src = inspect.getsource(_FaceFrame._build_ui)
        assert "_play_btn" in src or "Play" in src

    def test_build_ui_has_stop_button(self):
        import inspect
        from src.gui.character_builder_window import _FaceFrame
        src = inspect.getsource(_FaceFrame._build_ui)
        assert "_stop_btn" in src or "Stop" in src

    def test_build_ui_has_status_bar(self):
        import inspect
        from src.gui.character_builder_window import _FaceFrame
        src = inspect.getsource(_FaceFrame._build_ui)
        assert "_status_lbl" in src

    def test_build_ui_uses_three_panels(self):
        """Verify at least 3 panel regions are set up."""
        import inspect
        from src.gui.character_builder_window import _FaceFrame
        src = inspect.getsource(_FaceFrame._build_ui)
        # At minimum: left, centre, right panels
        panel_indicators = ["side=tk.LEFT", "fill=tk.BOTH"]
        found = sum(1 for p in panel_indicators if p in src)
        assert found >= 2


# ──────────────────────────────────────────────────────────────────────────────
#  Integration with validation_service hooks
# ──────────────────────────────────────────────────────────────────────────────

class TestFaceModeVsValidationService:
    """Verify that _FaceFrame's hook and bone lists align with validation_service."""

    def test_face_hook_list_contains_validation_required_hooks(self):
        """The hooks checked by _FaceFrame should include those in validation_service."""
        from src.gui.character_builder_window import _FaceFrame
        from src.core.validation_service import _HEAD_REQUIRED_HOOKS
        face_hook_names = {n for _, n, _ in _FaceFrame._HOOK_NODES}
        for hook in _HEAD_REQUIRED_HOOKS:
            assert hook in face_hook_names, \
                f"validation_service required hook '{hook}' not in _FaceFrame._HOOK_NODES"

    def test_face_bones_contain_validation_facial_bones(self):
        """_FaceFrame's facial bone list should include those in validation_service."""
        from src.gui.character_builder_window import _FaceFrame
        from src.core.validation_service import _FACIAL_BONES
        face_all_bones = {nn for _, nns, _ in _FaceFrame._FACIAL_BONES for nn in nns}
        for bone in _FACIAL_BONES:
            assert bone in face_all_bones, \
                f"validation_service facial bone '{bone}' not in _FaceFrame._FACIAL_BONES"


# ──────────────────────────────────────────────────────────────────────────────
#  Full Phase 3 character_builder_window module integrity
# ──────────────────────────────────────────────────────────────────────────────

class TestPhase3WindowIntegrity:

    def test_all_five_mode_frames_registered(self):
        import inspect
        from src.gui.character_builder_window import CharacterBuilderWindow, \
            _AssemblyFrame, _RigFrame, _FaceFrame, _PreviewFrame, _ExportFrame
        src = inspect.getsource(CharacterBuilderWindow._build_notebook)
        for cls_name in ["_AssemblyFrame", "_RigFrame", "_FaceFrame",
                         "_PreviewFrame", "_ExportFrame"]:
            assert cls_name in src, f"{cls_name} not registered in notebook"

    def test_mode_labels_correct_order(self):
        from src.gui.character_builder_window import _MODE_LABELS
        assert _MODE_LABELS == ["Assembly", "Rig", "Face", "Preview", "Export"]

    def test_rig_and_face_not_placeholders(self):
        """Neither _RigFrame nor _FaceFrame should have placeholder-only content."""
        import inspect
        from src.gui.character_builder_window import _RigFrame, _FaceFrame
        for cls in (_RigFrame, _FaceFrame):
            src = inspect.getsource(cls)
            # Should NOT have only a single Label with placeholder text
            assert "tk.Listbox" in src or "tk.Text" in src or "tk.Button" in src, \
                f"{cls.__name__} appears to be a placeholder-only frame"

    def test_character_builder_window_can_be_imported(self):
        import src.gui.character_builder_window as cbw
        assert cbw.CharacterBuilderWindow is not None

    def test_open_character_builder_function_exists(self):
        from src.gui.character_builder_window import open_character_builder
        assert callable(open_character_builder)

    def test_import_character_builder_returns_selector_and_groups(self):
        from src.gui.character_builder_window import _import_character_builder
        SkeletonSelector, BONE_GROUPS = _import_character_builder()
        assert hasattr(SkeletonSelector, 'select_all')
        assert "spine" in BONE_GROUPS
        assert "head" in BONE_GROUPS
