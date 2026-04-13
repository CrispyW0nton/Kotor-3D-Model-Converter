"""
test_v370_character_scene_validation.py
========================================
Tests for:
  • CharacterScene  (model_data.py)
  • SceneSlot       (model_data.py)
  • _make_asset_id  (model_data.py)
  • ValidationService / validate_scene (validation_service.py)

All tests use lightweight stubs (no real game files needed).
"""

import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src.core.model_data import (
    CharacterScene, SceneSlot, PartSlot, PART_SLOT_LABELS,
    KotorModel, ModelNode, NodeFlags, _make_asset_id,
)
from src.core.validation_service import (
    ValidationService, ValidationIssue, Severity, validate_scene,
)


# ──────────────────────────────────────────────────────────────────────────────
#  Helpers / Stubs
# ──────────────────────────────────────────────────────────────────────────────

def _make_node(name: str, *, is_mesh=False, is_skin=False, vertices=None,
               flags_extra: int = 0) -> ModelNode:
    """Return a minimal ModelNode for testing."""
    n = ModelNode(name=name)
    base_flag = int(NodeFlags.HEADER)
    if is_mesh:
        base_flag |= int(NodeFlags.MESH)
    if is_skin:
        base_flag |= int(NodeFlags.SKIN)
    n.flags = base_flag | flags_extra
    n.vertices = vertices or []
    return n


def _tree(*nodes) -> KotorModel:
    """Wrap a list of ModelNodes into a minimal KotorModel."""
    root = nodes[0]
    root.children = list(nodes[1:])
    for child in root.children:
        child.parent = root
    model = KotorModel(name="test_model", root_node=root)
    return model


def _head_model_minimal(supermodel: str = "S_Female02") -> KotorModel:
    """Head model with all required hooks and facial bones."""
    root = _make_node("gr_head_k1")
    root.vertices = [(0.0, 0.0, 0.0)]  # has geometry

    for hook_name in ("talkdummy", "headhook", "camerahook",
                      "cutscenedummy", "MaskHook", "GoggleHook",
                      "f_um_g", "f_jaw_g", "f_lmc_g", "f_rmc_g"):
        child = _make_node(hook_name)
        root.children.append(child)
        child.parent = root

    mesh = _make_node("face_mesh", is_mesh=True,
                      vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)])
    root.children.append(mesh)

    model = KotorModel(name="head_test", root_node=root, supermodel=supermodel)
    return model


def _body_model_minimal(supermodel: str = "S_Female02") -> KotorModel:
    """Body model with all required hooks."""
    root = _make_node("gr_body_k1")
    root.vertices = [(0.0, 0.0, 0.0)]

    for hook_name in ("headhook", "rhand", "lhand_g", "camerahook",
                      "chestconjure", "handconjure", "impact_bolt"):
        child = _make_node(hook_name)
        root.children.append(child)
        child.parent = root

    mesh = _make_node("body_mesh", is_mesh=True,
                      vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)])
    root.children.append(mesh)

    model = KotorModel(name="body_test", root_node=root, supermodel=supermodel)
    return model


# ──────────────────────────────────────────────────────────────────────────────
#  CharacterScene tests
# ──────────────────────────────────────────────────────────────────────────────

class TestCharacterScene:

    def test_empty_scene_is_empty(self):
        scene = CharacterScene(game_version="K1")
        assert scene.is_empty
        assert scene.all_models == []

    def test_assign_creates_slot(self):
        scene = CharacterScene(game_version="K1")
        model = _head_model_minimal()
        entry = scene.assign(PartSlot.HEAD_SHELL, model, resref="pfhc01")
        assert PartSlot.HEAD_SHELL in scene.slots
        assert entry.model is model
        assert entry.resref == "pfhc01"

    def test_assign_marks_dirty(self):
        scene = CharacterScene(game_version="K1")
        assert not scene.dirty
        scene.assign(PartSlot.HEAD_SHELL, None, resref="test")
        assert scene.dirty

    def test_get_model_returns_model(self):
        scene = CharacterScene(game_version="K1")
        model = _head_model_minimal()
        scene.assign(PartSlot.HEAD_SHELL, model, resref="pfhc01")
        assert scene.get_model(PartSlot.HEAD_SHELL) is model

    def test_get_model_missing_returns_none(self):
        scene = CharacterScene(game_version="K1")
        assert scene.get_model(PartSlot.HEADLESS_BODY) is None

    def test_clear_slot(self):
        scene = CharacterScene(game_version="K1")
        model = _head_model_minimal()
        scene.assign(PartSlot.HEAD_SHELL, model)
        scene.clear_slot(PartSlot.HEAD_SHELL)
        assert PartSlot.HEAD_SHELL not in scene.slots

    def test_head_and_body_properties(self):
        scene = CharacterScene(game_version="K1")
        hm = _head_model_minimal()
        bm = _body_model_minimal()
        scene.assign(PartSlot.HEAD_SHELL, hm, resref="pfhc01")
        scene.assign(PartSlot.HEADLESS_BODY, bm, resref="pfbcm")
        assert scene.head_model is hm
        assert scene.body_model is bm

    def test_mark_clean(self):
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEAD_SHELL, None)
        assert scene.dirty
        scene.mark_clean()
        assert not scene.dirty

    def test_all_models_includes_both(self):
        scene = CharacterScene(game_version="K1")
        hm = _head_model_minimal()
        bm = _body_model_minimal()
        scene.assign(PartSlot.HEAD_SHELL, hm)
        scene.assign(PartSlot.HEADLESS_BODY, bm)
        models = scene.all_models
        assert hm in models
        assert bm in models

    def test_summary_includes_resrefs(self):
        scene = CharacterScene(game_version="K1", character_name="Revan")
        scene.assign(PartSlot.HEAD_SHELL, None, resref="pfhc01")
        summary = scene.summary()
        assert "pfhc01" in summary
        assert "K1" in summary

    def test_assign_resref_lowercased(self):
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEAD_SHELL, None, resref="PFHC01")
        assert scene.slots[PartSlot.HEAD_SHELL].resref == "pfhc01"

    def test_scene_id_is_unique_per_instance(self):
        s1 = CharacterScene()
        s2 = CharacterScene()
        assert s1.scene_id != s2.scene_id

    def test_metadata_roundtrip(self):
        scene = CharacterScene()
        scene.metadata["export_fmt"] = "FBX"
        scene.metadata["camera"] = [0, 0, 5]
        assert scene.metadata["export_fmt"] == "FBX"
        assert scene.metadata["camera"] == [0, 0, 5]


# ──────────────────────────────────────────────────────────────────────────────
#  SceneSlot / asset_id tests
# ──────────────────────────────────────────────────────────────────────────────

class TestSceneSlot:

    def test_asset_id_auto_generated(self):
        slot = SceneSlot(slot=PartSlot.HEAD_SHELL, resref="pfhc01",
                         game_version="K1")
        assert slot.asset_id.startswith("gr:")
        assert "PFHC01" in slot.asset_id
        assert "K1" in slot.asset_id

    def test_asset_id_stable(self):
        id1 = _make_asset_id("pfhc01", "K1")
        id2 = _make_asset_id("pfhc01", "K1")
        assert id1 == id2

    def test_asset_id_differs_by_game(self):
        id_k1 = _make_asset_id("pfhc01", "K1")
        id_k2 = _make_asset_id("pfhc01", "K2")
        assert id_k1 != id_k2

    def test_asset_id_differs_by_resref(self):
        id_a = _make_asset_id("pfhc01", "K1")
        id_b = _make_asset_id("pfhc02", "K1")
        assert id_a != id_b

    def test_scene_asset_id_for(self):
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEAD_SHELL, None, resref="pfhc01")
        aid = scene.asset_id_for(PartSlot.HEAD_SHELL)
        assert aid is not None
        assert "PFHC01" in aid

    def test_scene_asset_id_missing_slot_returns_none(self):
        scene = CharacterScene(game_version="K1")
        assert scene.asset_id_for(PartSlot.HEADLESS_BODY) is None


# ──────────────────────────────────────────────────────────────────────────────
#  PartSlot / PART_SLOT_LABELS
# ──────────────────────────────────────────────────────────────────────────────

class TestPartSlot:

    def test_all_slots_have_labels(self):
        for slot in PartSlot:
            assert slot in PART_SLOT_LABELS, f"Missing label for {slot}"

    def test_slot_values_are_strings(self):
        for slot in PartSlot:
            assert isinstance(slot.value, str)

    def test_head_shell_value(self):
        assert PartSlot.HEAD_SHELL.value == "head_shell"

    def test_headless_body_value(self):
        assert PartSlot.HEADLESS_BODY.value == "headless_body"


# ──────────────────────────────────────────────────────────────────────────────
#  ValidationIssue
# ──────────────────────────────────────────────────────────────────────────────

class TestValidationIssue:

    def test_str_includes_severity_and_code(self):
        issue = ValidationIssue(
            severity=Severity.ERROR,
            code="HOOK_MISSING",
            message="headhook not found",
            slot=PartSlot.HEAD_SHELL,
            node="headhook",
        )
        s = str(issue)
        assert "ERROR" in s
        assert "HOOK_MISSING" in s
        assert "head_shell" in s
        assert "headhook" in s

    def test_is_error(self):
        e = ValidationIssue(Severity.ERROR, "X", "msg")
        w = ValidationIssue(Severity.WARNING, "X", "msg")
        assert e.is_error
        assert not w.is_error

    def test_is_warning(self):
        w = ValidationIssue(Severity.WARNING, "X", "msg")
        assert w.is_warning
        assert not ValidationIssue(Severity.ERROR, "X", "msg").is_warning

    def test_info_not_error_or_warning(self):
        i = ValidationIssue(Severity.INFO, "X", "msg")
        assert not i.is_error
        assert not i.is_warning


# ──────────────────────────────────────────────────────────────────────────────
#  ValidationService — NO_GEOMETRY
# ──────────────────────────────────────────────────────────────────────────────

class TestValidationNoGeometry:

    def test_empty_scene_warns_no_geometry(self):
        scene = CharacterScene(game_version="K1")
        issues = validate_scene(scene)
        codes = [i.code for i in issues]
        assert "NO_GEOMETRY" in codes

    def test_scene_with_geometry_no_warning(self):
        scene = CharacterScene(game_version="K1")
        model = _head_model_minimal()
        scene.assign(PartSlot.HEAD_SHELL, model)
        issues = validate_scene(scene)
        codes = [i.code for i in issues]
        assert "NO_GEOMETRY" not in codes

    def test_scene_with_none_model_still_warns(self):
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEAD_SHELL, None)  # assigned but model=None
        issues = validate_scene(scene)
        codes = [i.code for i in issues]
        assert "NO_GEOMETRY" in codes


# ──────────────────────────────────────────────────────────────────────────────
#  ValidationService — K1_K2_MISMATCH
# ──────────────────────────────────────────────────────────────────────────────

class TestValidationK1K2Mismatch:

    def test_mixed_game_versions_errors(self):
        scene = CharacterScene(game_version="K1")
        head = _head_model_minimal()
        body = _body_model_minimal()
        # Assign head as K1, body as K2
        entry_head = scene.assign(PartSlot.HEAD_SHELL, head, resref="pfhc01",
                                  game_version="K1")
        entry_body = scene.assign(PartSlot.HEADLESS_BODY, body, resref="pfbcm",
                                  game_version="K2")
        issues = validate_scene(scene)
        codes = [i.code for i in issues]
        assert "K1_K2_MISMATCH" in codes

    def test_same_game_version_no_mismatch(self):
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEAD_SHELL, _head_model_minimal(),
                     resref="pfhc01", game_version="K1")
        scene.assign(PartSlot.HEADLESS_BODY, _body_model_minimal(),
                     resref="pfbcm", game_version="K1")
        issues = validate_scene(scene)
        mismatch = [i for i in issues if i.code == "K1_K2_MISMATCH"]
        assert not mismatch

    def test_single_slot_no_mismatch(self):
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEAD_SHELL, _head_model_minimal(), game_version="K1")
        issues = validate_scene(scene)
        assert not any(i.code == "K1_K2_MISMATCH" for i in issues)


# ──────────────────────────────────────────────────────────────────────────────
#  ValidationService — SUPERMODEL_MISMATCH
# ──────────────────────────────────────────────────────────────────────────────

class TestValidationSupermodelMismatch:

    def test_mismatched_supermodels_error(self):
        scene = CharacterScene(game_version="K1")
        head = _head_model_minimal(supermodel="S_Female02")
        body = _body_model_minimal(supermodel="S_Male02")
        scene.assign(PartSlot.HEAD_SHELL, head)
        scene.assign(PartSlot.HEADLESS_BODY, body)
        issues = validate_scene(scene)
        codes = [i.code for i in issues]
        assert "SUPERMODEL_MISMATCH" in codes

    def test_matching_supermodels_no_error(self):
        scene = CharacterScene(game_version="K1")
        head = _head_model_minimal(supermodel="S_Female02")
        body = _body_model_minimal(supermodel="S_Female02")
        scene.assign(PartSlot.HEAD_SHELL, head)
        scene.assign(PartSlot.HEADLESS_BODY, body)
        issues = validate_scene(scene)
        assert not any(i.code == "SUPERMODEL_MISMATCH" for i in issues)

    def test_null_supermodel_ignored(self):
        """Models with NULL supermodel should not trigger mismatch."""
        scene = CharacterScene(game_version="K1")
        head = _head_model_minimal(supermodel="NULL")
        scene.assign(PartSlot.HEAD_SHELL, head)
        issues = validate_scene(scene)
        assert not any(i.code == "SUPERMODEL_MISMATCH" for i in issues)

    def test_unknown_supermodel_warns(self):
        scene = CharacterScene(game_version="K1")
        head = _head_model_minimal(supermodel="S_UNKNOWN_MODEL")
        scene.assign(PartSlot.HEAD_SHELL, head)
        issues = validate_scene(scene)
        assert any(i.code == "SUPERMODEL_UNKNOWN" for i in issues)


# ──────────────────────────────────────────────────────────────────────────────
#  ValidationService — HOOK_MISSING (head)
# ──────────────────────────────────────────────────────────────────────────────

class TestValidationHookMissingHead:

    def _head_without(self, *missing_hooks) -> KotorModel:
        """Head model missing specific hooks."""
        root = _make_node("head_root")
        root.vertices = [(0, 0, 0)]
        all_hooks = ["talkdummy", "headhook", "camerahook",
                     "cutscenedummy", "MaskHook", "GoggleHook",
                     "f_um_g", "f_jaw_g", "f_lmc_g", "f_rmc_g"]
        for hook_name in all_hooks:
            if hook_name not in missing_hooks:
                child = _make_node(hook_name)
                root.children.append(child)
                child.parent = root
        return KotorModel(name="head", root_node=root, supermodel="S_Female02")

    def test_missing_talkdummy_is_error(self):
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEAD_SHELL, self._head_without("talkdummy"))
        issues = validate_scene(scene)
        errs = [i for i in issues if i.code == "HOOK_MISSING" and i.is_error]
        node_names = [i.node for i in errs]
        assert "talkdummy" in node_names

    def test_missing_headhook_is_error(self):
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEAD_SHELL, self._head_without("headhook"))
        issues = validate_scene(scene)
        errs = [i for i in issues if i.code == "HOOK_MISSING" and i.is_error]
        node_names = [i.node for i in errs]
        assert "headhook" in node_names

    def test_missing_camerahook_is_warning(self):
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEAD_SHELL, self._head_without("camerahook"))
        issues = validate_scene(scene)
        warns = [i for i in issues if i.code == "HOOK_MISSING" and i.is_warning]
        assert any(i.node == "camerahook" for i in warns)

    def test_complete_head_no_hook_errors(self):
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEAD_SHELL, _head_model_minimal())
        issues = validate_scene(scene)
        hook_errors = [i for i in issues if i.code == "HOOK_MISSING" and i.is_error]
        assert not hook_errors

    def test_strict_mode_promotes_camerahook_to_error(self):
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEAD_SHELL, self._head_without("camerahook"))
        svc = ValidationService(scene, strict=True)
        issues = svc.validate()
        cam_issues = [i for i in issues if i.node == "camerahook" and i.code == "HOOK_MISSING"]
        assert any(i.is_error for i in cam_issues)


# ──────────────────────────────────────────────────────────────────────────────
#  ValidationService — HOOK_MISSING (body)
# ──────────────────────────────────────────────────────────────────────────────

class TestValidationHookMissingBody:

    def _body_without(self, *missing_hooks) -> KotorModel:
        root = _make_node("body_root")
        root.vertices = [(0, 0, 0)]
        all_hooks = ["headhook", "rhand", "lhand_g", "camerahook",
                     "chestconjure", "handconjure", "impact_bolt"]
        for hook_name in all_hooks:
            if hook_name not in missing_hooks:
                child = _make_node(hook_name)
                root.children.append(child)
                child.parent = root
        return KotorModel(name="body", root_node=root, supermodel="S_Female02")

    def test_missing_headhook_body_error(self):
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEADLESS_BODY, self._body_without("headhook"))
        issues = validate_scene(scene)
        errs = [i for i in issues if i.code == "HOOK_MISSING" and i.is_error]
        assert any(i.node == "headhook" for i in errs)

    def test_missing_rhand_body_error(self):
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEADLESS_BODY, self._body_without("rhand"))
        issues = validate_scene(scene)
        errs = [i for i in issues if i.code == "HOOK_MISSING" and i.is_error]
        assert any(i.node == "rhand" for i in errs)

    def test_complete_body_no_hook_errors(self):
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEADLESS_BODY, _body_model_minimal())
        issues = validate_scene(scene)
        hook_errors = [i for i in issues if i.code == "HOOK_MISSING" and i.is_error]
        assert not hook_errors


# ──────────────────────────────────────────────────────────────────────────────
#  ValidationService — BONE_MISSING (facial bones)
# ──────────────────────────────────────────────────────────────────────────────

class TestValidationBoneMissing:

    def test_missing_facial_bone_warns(self):
        # Head without f_um_g
        root = _make_node("head_root")
        root.vertices = [(0, 0, 0)]
        for name in ("talkdummy", "headhook", "f_jaw_g", "f_lmc_g", "f_rmc_g"):
            child = _make_node(name)
            root.children.append(child); child.parent = root
        model = KotorModel(name="h", root_node=root, supermodel="S_Female02")
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEAD_SHELL, model)
        issues = validate_scene(scene)
        bone_warns = [i for i in issues if i.code == "BONE_MISSING"]
        assert any(i.node == "f_um_g" for i in bone_warns)

    def test_body_slot_does_not_check_facial_bones(self):
        """Facial bone check runs only on HEAD_SHELL, not HEADLESS_BODY."""
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEADLESS_BODY, _body_model_minimal())
        issues = validate_scene(scene)
        assert not any(i.code == "BONE_MISSING" for i in issues)

    def test_complete_head_no_bone_missing(self):
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEAD_SHELL, _head_model_minimal())
        issues = validate_scene(scene)
        assert not any(i.code == "BONE_MISSING" for i in issues)


# ──────────────────────────────────────────────────────────────────────────────
#  ValidationService — skin weight rules
# ──────────────────────────────────────────────────────────────────────────────

class TestValidationWeights:

    def _skin_model_with_weights(self, weight_rows, supermodel="S_Female02") -> KotorModel:
        """Build a model with a skin mesh carrying the given weight rows."""
        root = _make_node("root")
        skin = _make_node("body_skin", is_skin=True,
                          vertices=[(i, 0.0, 0.0) for i in range(len(weight_rows))])
        skin.bone_weights  = weight_rows
        skin.bone_indices  = [[0] * len(row) for row in weight_rows]
        root.children.append(skin); skin.parent = root
        return KotorModel(name="m", root_node=root, supermodel=supermodel)

    def test_normalized_weights_no_warning(self):
        model = self._skin_model_with_weights(
            [[1.0, 0.0, 0.0, 0.0],
             [0.5, 0.5, 0.0, 0.0],
             [0.25, 0.25, 0.25, 0.25]]
        )
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEADLESS_BODY, model)
        issues = validate_scene(scene)
        weight_issues = [i for i in issues if i.code.startswith("WEIGHT")]
        assert not weight_issues

    def test_unnormalized_weights_warns(self):
        model = self._skin_model_with_weights([[0.5, 0.0, 0.0, 0.0]])  # sum=0.5
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEADLESS_BODY, model)
        issues = validate_scene(scene)
        codes = [i.code for i in issues]
        assert "WEIGHT_UNNORMALIZED" in codes

    def test_zero_sum_weights_warns(self):
        model = self._skin_model_with_weights([[0.0, 0.0, 0.0, 0.0]])
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEADLESS_BODY, model)
        issues = validate_scene(scene)
        codes = [i.code for i in issues]
        assert "WEIGHT_ZERO_SUM" in codes

    def test_weight_overflow_warns(self):
        # 5 influences — more than KotOR's limit of 4
        model = self._skin_model_with_weights([[0.2, 0.2, 0.2, 0.2, 0.2]])
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEADLESS_BODY, model)
        issues = validate_scene(scene)
        codes = [i.code for i in issues]
        assert "WEIGHT_OVERFLOW" in codes

    def test_unrigged_skin_mesh_warns(self):
        root = _make_node("root")
        skin = _make_node("unrigged", is_skin=True,
                          vertices=[(0, 0, 0)])
        skin.bone_weights = []
        skin.bone_indices = []
        root.children.append(skin); skin.parent = root
        model = KotorModel(name="m", root_node=root, supermodel="S_Female02")
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEADLESS_BODY, model)
        issues = validate_scene(scene)
        codes = [i.code for i in issues]
        assert "SKIN_MESH_UNRIGGED" in codes

    def test_max_weight_errors_truncation(self):
        """With many bad vertices, the validator shows a truncation info notice."""
        bad_rows = [[0.5] * 4] * 30  # 30 unnormalized rows (sum=2.0 each)
        model = self._skin_model_with_weights(bad_rows)
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEADLESS_BODY, model)
        svc = ValidationService(scene, max_weight_errors=5)
        issues = svc.validate()
        codes = [i.code for i in issues]
        assert "WEIGHT_ERRORS_TRUNCATED" in codes


# ──────────────────────────────────────────────────────────────────────────────
#  ValidationService — ValidationService.passed property
# ──────────────────────────────────────────────────────────────────────────────

class TestValidationPassed:

    def test_passed_true_when_no_errors(self):
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEAD_SHELL, _head_model_minimal())
        scene.assign(PartSlot.HEADLESS_BODY, _body_model_minimal())
        svc = ValidationService(scene)
        svc.validate()
        # May have warnings (unexpected hooks, etc.) but should not have errors
        assert svc.passed

    def test_passed_false_when_errors_present(self):
        scene = CharacterScene(game_version="K1")
        # Mix K1 + K2 → K1_K2_MISMATCH error
        scene.assign(PartSlot.HEAD_SHELL, _head_model_minimal(), game_version="K1")
        scene.assign(PartSlot.HEADLESS_BODY, _body_model_minimal(), game_version="K2")
        svc = ValidationService(scene)
        svc.validate()
        assert not svc.passed

    def test_errors_and_warnings_properties(self):
        scene = CharacterScene(game_version="K1")
        # Assign only head (body missing = NO_GEOMETRY? No. We have head geometry.)
        scene.assign(PartSlot.HEAD_SHELL, _head_model_minimal())
        svc = ValidationService(scene)
        issues = svc.validate()
        assert isinstance(svc.errors, list)
        assert isinstance(svc.warnings, list)
        assert all(i.is_error for i in svc.errors)
        assert all(i.is_warning for i in svc.warnings)


# ──────────────────────────────────────────────────────────────────────────────
#  validate_scene convenience function
# ──────────────────────────────────────────────────────────────────────────────

class TestValidateSceneFunction:

    def test_returns_list(self):
        scene = CharacterScene(game_version="K1")
        result = validate_scene(scene)
        assert isinstance(result, list)

    def test_strict_kwarg_accepted(self):
        scene = CharacterScene(game_version="K1")
        result = validate_scene(scene, strict=True)
        assert isinstance(result, list)

    def test_all_items_are_validation_issues(self):
        scene = CharacterScene(game_version="K1")
        result = validate_scene(scene)
        for item in result:
            assert isinstance(item, ValidationIssue)


# ──────────────────────────────────────────────────────────────────────────────
#  Integration: full pass with head + body
# ──────────────────────────────────────────────────────────────────────────────

class TestIntegrationFullScene:

    def test_complete_k1_scene_passes(self):
        """A fully assembled K1 scene with correct supermodel should pass validation."""
        scene = CharacterScene(game_version="K1")
        head = _head_model_minimal(supermodel="S_Female02")
        body = _body_model_minimal(supermodel="S_Female02")
        scene.assign(PartSlot.HEAD_SHELL, head, resref="pfhc01", game_version="K1")
        scene.assign(PartSlot.HEADLESS_BODY, body, resref="pfbcm", game_version="K1")
        svc = ValidationService(scene)
        issues = svc.validate()
        assert svc.passed, f"Expected pass, got errors: {[str(i) for i in svc.errors]}"

    def test_k1_k2_mismatch_detected_in_full_scene(self):
        scene = CharacterScene(game_version="K1")
        head = _head_model_minimal(supermodel="S_Female02")
        body = _body_model_minimal(supermodel="S_Male02")
        scene.assign(PartSlot.HEAD_SHELL, head, game_version="K1")
        scene.assign(PartSlot.HEADLESS_BODY, body, game_version="K2")
        issues = validate_scene(scene)
        assert any(i.code == "K1_K2_MISMATCH" for i in issues)
        assert any(i.code == "SUPERMODEL_MISMATCH" for i in issues)

    def test_scene_game_version_propagated(self):
        scene = CharacterScene(game_version="K2")
        assert scene.game_version == "K2"
        head = _head_model_minimal(supermodel="S_Female02")
        entry = scene.assign(PartSlot.HEAD_SHELL, head, game_version="K2")
        assert entry.game_version == "K2"
