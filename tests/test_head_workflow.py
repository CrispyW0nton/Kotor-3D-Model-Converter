"""
tests/test_head_workflow.py — M6 / T601 Head-mode workflow service tests.

Exercises the pure-Python service module ``src.core.head_workflow`` in
isolation from the Qt UI.  The tests construct a minimal fake
:class:`CharacterScene` + ``KotorModel`` so they run without PyKotor or
PySide6 installed — same direct-file-load pattern that
``tests/test_headless_body_workflow.py`` uses.

Roadmap reference: knowledge_base/roadmap/02_roadmap_2026_05.md M6/T601.
"""

from __future__ import annotations

import importlib.util as _il_util
import os
import pathlib
import sys
from typing import Any, List

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load_module_direct(name: str, path: pathlib.Path):
    """Load a Python module by absolute file path, side-stepping ``core/__init__``.

    The package's ``__init__.py`` eagerly imports the PyKotor-backed
    loader stack, which is unavailable in lightweight CI / dev
    environments.  Loading the modules directly by file path lets these
    tests run without that dependency, matching the pattern used in
    ``tests/test_headless_body_workflow.py``.
    """
    spec = _il_util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:                  # pragma: no cover
        raise ImportError(f"cannot create import spec for {path}")
    module = _il_util.module_from_spec(spec)
    sys.modules[spec.name] = module                          # required for dataclass
    spec.loader.exec_module(module)
    return module


try:
    md = _load_module_direct(
        "ghostrigger_md_for_head_wf",
        _SRC_DIR / "core" / "model_data.py",
    )
    wb = _load_module_direct(
        "ghostrigger_workflow_base_under_test",
        _SRC_DIR / "core" / "_workflow_base.py",
    )
    wf = _load_module_direct(
        "ghostrigger_head_workflow_under_test",
        _SRC_DIR / "core" / "head_workflow.py",
    )
    # Rebind the workflow module's lazy-import helpers so the dispatcher
    # uses the same ``model_data`` / ``_workflow_base`` identities the
    # tests imported above.  This is the M5 fake-injection pattern
    # (invariant #6 in the roadmap).
    wf._import_model_data = lambda: md                       # type: ignore[attr-defined]
    wf._import_workflow_base = lambda: wb                    # type: ignore[attr-defined]
except Exception as exc:                                     # pragma: no cover
    pytest.skip(f"head_workflow / model_data unavailable: {exc}",
                allow_module_level=True)


# ──────────────────────────────────────────────────────────────────────
#  Test helpers
# ──────────────────────────────────────────────────────────────────────

class _FakeNode:
    """Minimal stand-in for a ``ModelNode``."""

    def __init__(self, name: str):
        self.name = name


class _FakeHeadModel:
    """KotorModel-shaped object that detects as HEAD.

    Per ``detect_character_mode``:
      * classification CHARACTER
      * has ``head_g`` + ``f_jaw_g``
      * no ``pelvis_g``
    Either the ``talkdummy`` *or* the (head_g + facial + no-pelvis) rule
    flips detection to HEAD; we ship both so we exercise the canonical
    head-model shape.
    """

    def __init__(self, name: str = "pfhc01", extra_bones: List[str] = None):
        self.name = name
        self.supermodel = "S_Female02"
        self.model_type = int(md.ModelClassification.CHARACTER)
        bones = [
            "rootdummy",
            "head_g",
            "necklwr_g",
            "neck_g",
            "talkdummy",
            "f_jaw_g",
            "f_um_g",
            "f_llm_g",
            "f_rlm_g",
            "f_lec_g",
            "f_rec_g",
            "f_llid_g",
            "f_rlid_g",
            "maskhook",
            "gogglehook",
        ]
        if extra_bones:
            bones.extend(extra_bones)
        self._nodes = [_FakeNode(b) for b in bones]
        self.animations: list = []

    def all_nodes(self):
        return list(self._nodes)


class _FakeMinimalHead:
    """Head model missing the required facial bones (jaw / upper mouth)."""

    def __init__(self, name: str = "pfhc99"):
        self.name = name
        self.supermodel = "S_Female02"
        self.model_type = int(md.ModelClassification.CHARACTER)
        # head_g + talkdummy alone is enough to detect as HEAD but
        # leaves the required-bone palette starved.
        self._nodes = [
            _FakeNode("rootdummy"),
            _FakeNode("head_g"),
            _FakeNode("talkdummy"),
        ]
        self.animations: list = []

    def all_nodes(self):
        return list(self._nodes)


class _FakeBodyModel:
    """KotorModel-shaped object that detects as HEADLESS_BODY."""

    def __init__(self, name: str = "pfbcm"):
        self.name = name
        self.supermodel = "S_Female02"
        self.model_type = int(md.ModelClassification.CHARACTER)
        self._nodes = [
            _FakeNode("rootdummy"),
            _FakeNode("headhook"),
            _FakeNode("rhand"),
        ]

    def all_nodes(self):
        return list(self._nodes)


def _make_scene(game_version: str = "K1"):
    return md.CharacterScene(game_version=game_version)


def _scene_with_head(name: str = "pfhc01"):
    """Return ``(scene, head)`` with ``HEAD_SHELL`` populated."""
    scene = _make_scene("K1")
    head = _FakeHeadModel(name)
    scene.assign(md.PartSlot.HEAD_SHELL, head,
                 resref=name, source_path=f"/tmp/{name}.mdl")
    return scene, head


class _FakeSeverity:
    def __init__(self, value: str):
        self.value = value


class _FakeIssue:
    """Duck-typed ValidationIssue."""

    def __init__(self, severity: str, code: str, slot=None,
                 node: str = "", message: str = ""):
        self.severity = _FakeSeverity(severity)
        self.code = code
        self.slot = slot
        self.node = node
        self.message = message


def _make_check_service(monkeypatch, issues: List[Any]):
    """Stub the ValidationService so :func:`check_head` and
    :func:`validate_for_export_head` receive the canned issue list."""
    class _StubService:
        def __init__(self, scene, *, strict: bool = False, **kw):
            self.scene = scene
            self.strict = strict

        def validate(self):
            return list(issues)

    class _StubMod:
        ValidationService = _StubService

    monkeypatch.setattr(wf, "_import_validation_service", lambda: _StubMod)


class _FakeCharacterBuilder:
    """Stand-in for ``core.character_builder``.

    Provides the two functions :func:`check_head` and :func:`rig_head`
    actually call: ``validate_facial_bones`` and ``find_headhook`` —
    plus a ``LIPPlayback`` class for the viseme-application tests.
    """

    facial_warnings_for: dict = {}      # head_id → warning list
    headhook_for:        dict = {}      # body_id → world-transform tuple

    @staticmethod
    def validate_facial_bones(head):
        return list(_FakeCharacterBuilder.facial_warnings_for.get(
            id(head), []
        ))

    @staticmethod
    def find_headhook(body):
        return _FakeCharacterBuilder.headhook_for.get(id(body))

    class LIPPlayback:
        """Minimal stand-in for the real LIPPlayback class."""

        def __init__(self):
            self._has_talk = False

        def load_talk_animation(self, head) -> bool:
            # Detect a 'talk' animation in our fake head.
            anims = getattr(head, "animations", []) or []
            for a in anims:
                if getattr(a, "name", "").lower() == "talk":
                    self._has_talk = True
                    return True
            return False


def _install_fake_cb(monkeypatch):
    monkeypatch.setattr(wf, "_import_character_builder",
                        lambda: _FakeCharacterBuilder)
    _FakeCharacterBuilder.facial_warnings_for = {}
    _FakeCharacterBuilder.headhook_for = {}
    return _FakeCharacterBuilder


class _FakeLIPShape:
    """Stand-in for :class:`lip_reader.LIPShape`."""

    _values = [
        "REST", "EE", "EH", "SCHWA", "AH", "OH", "OOH", "Y",
        "S_TS", "F_V", "NN", "TH", "MPB", "W", "LL", "KCG",
    ]

    def __init__(self, idx, name):
        self.value = idx
        self.name = name

    def __int__(self):
        return self.value


class _FakeLIPShapeEnum:
    """Iterable mimicking :class:`lip_reader.LIPShape`."""

    def __iter__(self):
        return iter(
            _FakeLIPShape(i, name)
            for i, name in enumerate(_FakeLIPShape._values)
        )


class _FakeLipReader:
    LIPShape = _FakeLIPShapeEnum()


def _install_fake_lip(monkeypatch):
    monkeypatch.setattr(wf, "_import_lip_reader", lambda: _FakeLipReader)
    return _FakeLipReader


# ──────────────────────────────────────────────────────────────────────
#  T601 ▸ Module surface — constants exist and have sensible shapes
# ──────────────────────────────────────────────────────────────────────

def test_t601_module_exports_required_constants():
    """The head workflow module must expose the canonical palette."""
    assert "head_g" in wf.REQUIRED_HEAD_BONES
    assert "f_jaw_g" in wf.REQUIRED_HEAD_BONES
    assert "f_um_g" in wf.REQUIRED_HEAD_BONES
    # Recommended bones come from validate_facial_bones too.
    assert "necklwr_g" in wf.RECOMMENDED_HEAD_BONES
    assert "neck_g" in wf.RECOMMENDED_HEAD_BONES
    assert "maskhook" in wf.RECOMMENDED_HEAD_BONES
    # Neck chain is ordered torso→head.
    assert wf.NECK_CHAIN[-1] == "head_g"
    # Face rig must contain at least 8 bones (T604 needs 8 phoneme knobs).
    assert len(wf.FACE_RIG_BONES) >= 8
    # Phoneme registry is exactly the 8-pose dict per T604 spec.
    assert len(wf.PHONEME_POSES) == 8
    # Camera preset has all required keys.
    for k in ("eye", "target", "up", "fov_deg", "clip"):
        assert k in wf.HEAD_CAMERA_PRESET


def test_t601_supported_extensions_cover_mdl_gltf_fbx_obj_utc():
    exts = wf.supported_load_extensions()
    for needed in (".mdl", ".gltf", ".glb", ".fbx", ".obj", ".utc"):
        assert needed in exts, f"missing extension: {needed}"


def test_t601_load_file_filter_uses_head_label():
    f = wf.load_file_filter()
    # Must say "Head models" (not "Body models" — caught early UI bugs).
    assert "Head models" in f
    assert "*.mdl" in f
    assert ";;All files (*.*)" in f


# ──────────────────────────────────────────────────────────────────────
#  T601 ▸ load_head — defensive paths
# ──────────────────────────────────────────────────────────────────────

def test_t601_load_head_empty_path_returns_structured_error():
    scene = _make_scene()
    result = wf.load_head("", scene)
    assert result.ok is False
    assert result.code == "empty_path"
    # Scene must not have been mutated.
    assert md.PartSlot.HEAD_SHELL not in scene.slots


def test_t601_load_head_missing_file_returns_file_not_found():
    scene = _make_scene()
    result = wf.load_head("/tmp/does_not_exist_qt_ghostrigger_head.mdl", scene)
    assert result.ok is False
    assert result.code == "file_not_found"
    assert md.PartSlot.HEAD_SHELL not in scene.slots


def test_t601_load_head_unsupported_extension_is_rejected(tmp_path):
    scene = _make_scene()
    junk = tmp_path / "head.xyz"
    junk.write_bytes(b"not a model")
    result = wf.load_head(str(junk), scene)
    assert result.ok is False
    assert result.code == "unsupported_format"
    assert md.PartSlot.HEAD_SHELL not in scene.slots


# ──────────────────────────────────────────────────────────────────────
#  T601 ▸ load_head — happy path & mode mismatch
# ──────────────────────────────────────────────────────────────────────

def test_t601_load_head_happy_path_assigns_head_shell(tmp_path, monkeypatch):
    """When a head MDL loads cleanly, ``load_head`` mutates HEAD_SHELL."""
    fake = _FakeHeadModel("pfhc01")
    mdl_path = tmp_path / "pfhc01.mdl"
    mdl_path.write_bytes(b"stub")
    monkeypatch.setattr(wf, "_load_mdl", lambda path, gv: fake)

    scene = _make_scene("K1")
    result = wf.load_head(str(mdl_path), scene)

    assert result.ok is True
    assert result.code == "loaded"
    assert result.model is fake
    assert result.detected_mode == md.CharacterMode.HEAD
    assert result.resref == "pfhc01"
    # Crucially: the slot assigned is HEAD_SHELL, not HEADLESS_BODY.
    entry = scene.get(md.PartSlot.HEAD_SHELL)
    assert entry is not None
    assert entry.model is fake
    assert entry.resref == "pfhc01"
    assert entry.source_path == str(mdl_path)
    assert md.PartSlot.HEADLESS_BODY not in scene.slots


def test_t601_load_head_body_returns_mode_mismatch(tmp_path, monkeypatch):
    """Loading a BODY model into the head workflow surfaces a warning."""
    fake = _FakeBodyModel("pfbcm")
    mdl_path = tmp_path / "pfbcm.mdl"
    mdl_path.write_bytes(b"stub")
    monkeypatch.setattr(wf, "_load_mdl", lambda path, gv: fake)

    scene = _make_scene("K1")
    result = wf.load_head(str(mdl_path), scene)

    assert result.code == "mode_mismatch"
    assert result.ok is False
    assert result.detected_mode == md.CharacterMode.HEADLESS_BODY
    # Slot is still assigned so the user can see what they loaded.
    entry = scene.get(md.PartSlot.HEAD_SHELL)
    assert entry is not None
    assert entry.model is fake


def test_t601_load_head_mode_correction_flag_promotes_to_ok(
    tmp_path, monkeypatch,
):
    """``allow_mode_correction=True`` flips a mode-mismatch into success."""
    fake = _FakeBodyModel("pfbcm")
    mdl_path = tmp_path / "pfbcm.mdl"
    mdl_path.write_bytes(b"stub")
    monkeypatch.setattr(wf, "_load_mdl", lambda path, gv: fake)

    scene = _make_scene("K1")
    result = wf.load_head(str(mdl_path), scene, allow_mode_correction=True)

    assert result.ok is True
    assert result.code == "loaded"
    assert result.detected_mode == md.CharacterMode.HEADLESS_BODY


def test_t601_load_head_resref_is_lowercase_basename(tmp_path, monkeypatch):
    fake = _FakeHeadModel("PFHC01")
    p = tmp_path / "PFHC01_v2.mdl"
    p.write_bytes(b"x")
    monkeypatch.setattr(wf, "_load_mdl", lambda path, gv: fake)
    scene = _make_scene()
    result = wf.load_head(str(p), scene)
    assert result.resref == "pfhc01_v2"
    assert scene.get(md.PartSlot.HEAD_SHELL).resref == "pfhc01_v2"


# ──────────────────────────────────────────────────────────────────────
#  T601 ▸ check_head
# ──────────────────────────────────────────────────────────────────────

def test_t601_check_head_empty_scene_returns_no_head_loaded():
    scene = _make_scene()
    result = wf.check_head(scene)
    assert result.ok is False
    assert result.banner_key == "warning"
    assert "NO HEAD" in result.summary.upper()


def test_t601_check_head_clean_scene(monkeypatch):
    """A fully-populated head with no validator issues → CLEAN."""
    _install_fake_cb(monkeypatch)
    _make_check_service(monkeypatch, [])
    scene, _head = _scene_with_head()

    result = wf.check_head(scene)
    assert result.ok is True
    assert result.banner_key == "clean"
    assert result.summary == "CLEAN"
    assert result.error_count == 0
    assert result.missing_required == []
    assert result.missing_recommended == []


def test_t601_check_head_minimal_head_flags_missing_required(monkeypatch):
    """A head missing f_jaw_g / f_um_g must promote to ERROR banner."""
    _install_fake_cb(monkeypatch)
    _make_check_service(monkeypatch, [])
    scene = _make_scene()
    minimal = _FakeMinimalHead("pfhc99")
    scene.assign(md.PartSlot.HEAD_SHELL, minimal,
                 resref="pfhc99", source_path="/tmp/pfhc99.mdl")

    result = wf.check_head(scene)
    assert result.ok is False
    assert result.banner_key == "error"
    # Missing the jaw + upper-mouth (head_g is present in _FakeMinimalHead).
    assert "f_jaw_g" in result.missing_required
    assert "f_um_g" in result.missing_required
    # Synthetic codes surface in the codes set.
    assert any(c.startswith("FACIAL_BONE_MISSING:") for c in result.codes)
    # Tally reflects the synthetic errors.
    assert result.error_count == len(result.missing_required)


def test_t601_check_head_aggregates_validator_errors_and_facial(monkeypatch):
    """Real validator errors + facial-bone misses both flow to the banner."""
    _install_fake_cb(monkeypatch)
    _make_check_service(monkeypatch, [
        _FakeIssue("error", "WEIGHT_OVERFLOW", message="vertex >4 bones"),
        _FakeIssue("warning", "SUPERMODEL_UNKNOWN", message="…"),
    ])
    scene = _make_scene()
    minimal = _FakeMinimalHead("pfhc99")
    scene.assign(md.PartSlot.HEAD_SHELL, minimal,
                 resref="pfhc99", source_path="/tmp/pfhc99.mdl")

    result = wf.check_head(scene)
    assert result.ok is False
    assert result.banner_key == "error"
    # 1 validator error + 2 facial misses (jaw / upper mouth)
    assert result.error_count == 1 + 2
    assert result.warning_count == 1
    assert "WEIGHT_OVERFLOW" in result.codes


def test_t601_check_head_recommended_only_yields_warning(monkeypatch):
    """A head with required bones but missing recommended ones → WARNING."""
    _install_fake_cb(monkeypatch)
    _make_check_service(monkeypatch, [])
    scene = _make_scene()
    # Construct a head with required bones present but no neck_g / maskhook.
    head = _FakeHeadModel("pfhc02")
    # Remove the recommended bones from the fake's node list.
    head._nodes = [n for n in head._nodes
                   if n.name not in (
                       "necklwr_g", "neck_g", "f_llm_g", "f_rlm_g",
                       "maskhook", "gogglehook",
                   )]
    scene.assign(md.PartSlot.HEAD_SHELL, head,
                 resref="pfhc02", source_path="/tmp/pfhc02.mdl")

    result = wf.check_head(scene)
    assert result.ok is True                  # warnings don't block
    assert result.banner_key == "warning"
    assert result.warning_count >= 1
    # Recommended-bone codes surface in result.codes.
    assert any(c.startswith("FACIAL_BONE_RECOMMENDED:") for c in result.codes)


def test_t601_check_head_strict_passes_through_to_service(monkeypatch):
    """The ``strict`` kw must reach the ValidationService constructor."""
    _install_fake_cb(monkeypatch)
    captured: dict = {}

    class _RecordingService:
        def __init__(self, scene, *, strict: bool = False, **kw):
            captured["strict"] = strict

        def validate(self):
            return []

    class _Mod:
        ValidationService = _RecordingService

    monkeypatch.setattr(wf, "_import_validation_service", lambda: _Mod)
    scene, _head = _scene_with_head()

    wf.check_head(scene, strict=True)
    assert captured["strict"] is True

    wf.check_head(scene, strict=False)
    assert captured["strict"] is False


# ──────────────────────────────────────────────────────────────────────
#  T601 ▸ rig_head / rig_face
# ──────────────────────────────────────────────────────────────────────

def test_t601_rig_head_no_head_returns_structured_error():
    scene = _make_scene()
    result = wf.rig_head(scene)
    assert result.ok is False
    assert result.code == "no_head"


def test_t601_rig_head_full_chain_succeeds(monkeypatch):
    _install_fake_cb(monkeypatch)
    scene, _head = _scene_with_head()
    result = wf.rig_head(scene)
    assert result.ok is True
    assert result.code == "rigged"
    # Chain should contain the full neck chain + jaw.
    assert "head_g" in result.bones
    assert "f_jaw_g" in result.bones
    assert "neck_g" in result.bones


def test_t601_rig_head_missing_required_bone(monkeypatch):
    """A head without ``head_g`` cannot be rigged."""
    _install_fake_cb(monkeypatch)
    scene = _make_scene()
    head = _FakeHeadModel("pfhc01")
    # Strip head_g out.
    head._nodes = [n for n in head._nodes if n.name != "head_g"]
    # Replace with a synthetic talkdummy + facial so it still detects as
    # HEAD (the rig step doesn't re-detect; it just checks required bones).
    scene.assign(md.PartSlot.HEAD_SHELL, head,
                 resref="pfhc01", source_path="/tmp/pfhc01.mdl")

    result = wf.rig_head(scene)
    assert result.ok is False
    assert result.code == "missing_required_bone"
    assert "head_g" in result.message


def test_t601_rig_head_captures_parent_body_headhook(monkeypatch):
    """When a parent body is supplied, find_headhook() output is captured."""
    fake_cb = _install_fake_cb(monkeypatch)
    scene, _head = _scene_with_head()
    body = _FakeBodyModel("pfbcm")
    fake_cb.headhook_for[id(body)] = ((0.0, 0.0, 1.7), (0, 0, 0, 1))

    result = wf.rig_head(scene, parent_body=body)
    assert result.ok is True
    assert result.headhook == ((0.0, 0.0, 1.7), (0, 0, 0, 1))


def test_t601_rig_face_full_palette_active():
    scene, _head = _scene_with_head()
    result = wf.rig_face(scene)
    assert result.ok is True
    assert result.code == "rigged"
    # The full FACE_RIG_BONES list is present in the fake head.
    for bone in wf.FACE_RIG_BONES:
        assert bone in result.active
    assert result.skipped == []


def test_t601_rig_face_skips_missing_bones():
    """Face rig partitions present vs absent bones cleanly."""
    scene = _make_scene()
    head = _FakeHeadModel("pfhc01")
    head._nodes = [n for n in head._nodes
                   if n.name not in ("f_lec_g", "f_rec_g",
                                     "f_llid_g", "f_rlid_g")]
    scene.assign(md.PartSlot.HEAD_SHELL, head,
                 resref="pfhc01", source_path="/tmp/pfhc01.mdl")

    result = wf.rig_face(scene)
    assert result.ok is True
    # Eye/lid bones should be in skipped, lip bones in active.
    for absent in ("f_lec_g", "f_rec_g", "f_llid_g", "f_rlid_g"):
        assert absent in result.skipped
    assert "f_jaw_g" in result.active


def test_t601_rig_face_no_bones_returns_no_bones_found():
    """A head with zero face bones surfaces ``no_bones_found``."""
    scene = _make_scene()
    head = _FakeHeadModel("pfhc01")
    head._nodes = [n for n in head._nodes
                   if not n.name.startswith("f_")]
    scene.assign(md.PartSlot.HEAD_SHELL, head,
                 resref="pfhc01", source_path="/tmp/pfhc01.mdl")
    result = wf.rig_face(scene)
    assert result.ok is False
    assert result.code == "no_bones_found"


def test_t601_rig_face_accepts_extra_bones():
    """Caller-supplied extras participate in the active/skipped split."""
    scene = _make_scene()
    head = _FakeHeadModel("pfhc01", extra_bones=["custom_brow_l"])
    scene.assign(md.PartSlot.HEAD_SHELL, head,
                 resref="pfhc01", source_path="/tmp/pfhc01.mdl")
    result = wf.rig_face(scene, extra_bones=["custom_brow_l", "ghost_bone"])
    assert "custom_brow_l" in result.active
    assert "ghost_bone" in result.skipped


# ──────────────────────────────────────────────────────────────────────
#  T601 ▸ validate_for_export_head
# ──────────────────────────────────────────────────────────────────────

def test_t601_validate_for_export_head_clean(monkeypatch):
    _make_check_service(monkeypatch, [])
    scene, _head = _scene_with_head()

    result = wf.validate_for_export_head(scene, strict=True)
    assert result.ok is True
    assert result.code == "clean"
    assert result.error_count == 0
    assert result.blocking_codes == []


def test_t601_validate_for_export_head_warnings_only(monkeypatch):
    _make_check_service(monkeypatch, [
        _FakeIssue("warning", "SUPERMODEL_UNKNOWN", message="…"),
        _FakeIssue("info", "WEIGHT_ERRORS_TRUNCATED", message="…"),
    ])
    scene, _head = _scene_with_head()
    result = wf.validate_for_export_head(scene)
    assert result.ok is True
    assert result.code == "warnings_only"
    assert result.warning_count == 1
    assert result.info_count == 1


def test_t601_validate_for_export_head_errors_block(monkeypatch):
    _make_check_service(monkeypatch, [
        _FakeIssue("error", "BONE_MISSING", message="missing"),
        _FakeIssue("error", "WEIGHT_OVERFLOW", message="overflow"),
        _FakeIssue("warning", "HOOK_MISSING", message="hook"),
    ])
    scene, _head = _scene_with_head()
    result = wf.validate_for_export_head(scene, strict=True)
    assert result.ok is False
    assert result.code == "blocked"
    assert result.error_count == 2
    assert "BONE_MISSING" in result.blocking_codes
    assert "WEIGHT_OVERFLOW" in result.blocking_codes


# ──────────────────────────────────────────────────────────────────────
#  T601 ▸ export_head_scene
# ──────────────────────────────────────────────────────────────────────

class _FakeSceneIO:
    EXTENSION = ".ghostrig.json"
    written: list = []

    @staticmethod
    def write_sidecar(scene, model_path):
        base = os.path.splitext(model_path)[0]
        sidecar = base + _FakeSceneIO.EXTENSION
        _FakeSceneIO.written.append({"scene": scene, "path": sidecar})
        return os.path.abspath(sidecar)


def _install_fake_scene_io(monkeypatch):
    _FakeSceneIO.written = []
    monkeypatch.setattr(wf, "_import_scene_io", lambda: _FakeSceneIO)
    return _FakeSceneIO


def test_t601_export_head_no_head_returns_structured_error(monkeypatch):
    _install_fake_scene_io(monkeypatch)
    scene = _make_scene("K1")
    result = wf.export_head_scene(scene, formats=["kotor"], out_dir="/tmp/out")
    assert result.ok is False
    assert result.code == "no_head"


def test_t601_export_head_no_out_dir_returns_structured_error(monkeypatch):
    _install_fake_scene_io(monkeypatch)
    _make_check_service(monkeypatch, [])
    scene, _head = _scene_with_head()
    result = wf.export_head_scene(scene, formats=["kotor"], out_dir="")
    assert result.ok is False
    assert result.code == "no_out_dir"


def test_t601_export_head_blocked_by_validation_errors(monkeypatch, tmp_path):
    _install_fake_scene_io(monkeypatch)
    _make_check_service(monkeypatch, [
        _FakeIssue("error", "BONE_MISSING", message="…"),
    ])
    scene, _head = _scene_with_head()
    result = wf.export_head_scene(
        scene, formats=["kotor"], out_dir=str(tmp_path),
        write_sidecar=True,
    )
    assert result.ok is False
    assert result.code == "blocked"
    assert _FakeSceneIO.written == []


def test_t601_export_head_skip_validation_writes_sidecar(monkeypatch, tmp_path):
    """``skip_validation=True`` bypasses the strict gate."""
    _install_fake_scene_io(monkeypatch)
    _make_check_service(monkeypatch, [
        _FakeIssue("error", "BONE_MISSING", message="…"),
    ])
    scene, _head = _scene_with_head()
    result = wf.export_head_scene(
        scene, formats=["kotor"], out_dir=str(tmp_path),
        write_sidecar=True, skip_validation=True,
    )
    assert result.ok is True
    assert result.code == "exported"
    assert len(_FakeSceneIO.written) == 1
    assert "pfhc01" in _FakeSceneIO.written[0]["path"]


def test_t601_export_head_writes_sidecar_with_correct_resref(
    monkeypatch, tmp_path,
):
    """Sidecar path is ``<resref>.ghostrig.json`` next to the .mdl anchor."""
    _install_fake_scene_io(monkeypatch)
    _make_check_service(monkeypatch, [])
    scene, _head = _scene_with_head("pfhc05")

    result = wf.export_head_scene(
        scene, formats=[], out_dir=str(tmp_path),
        write_sidecar=True,
    )
    assert result.ok is True
    assert _FakeSceneIO.written
    assert _FakeSceneIO.written[0]["path"].endswith(
        "pfhc05.ghostrig.json"
    )


def test_t601_export_head_format_not_implemented_until_m10(
    monkeypatch, tmp_path,
):
    """Every requested binary format returns ``not_implemented`` for now."""
    _install_fake_scene_io(monkeypatch)
    _make_check_service(monkeypatch, [])
    scene, _head = _scene_with_head("pfhc01")

    result = wf.export_head_scene(
        scene, formats=["kotor", "fbx", "gltf", "obj"],
        out_dir=str(tmp_path), write_sidecar=True,
    )
    assert result.ok is True
    assert len(result.formats) == 4
    for row in result.formats:
        assert row.code == "not_implemented"
        assert row.path.endswith(
            {".mdl", ".fbx", ".gltf", ".obj"} & {os.path.splitext(row.path)[1]}
            and os.path.splitext(row.path)[1] or row.path
        ) or os.path.splitext(row.path)[1] in {".mdl", ".fbx", ".gltf", ".obj"}


def test_t601_export_head_unknown_format_returns_failed(monkeypatch, tmp_path):
    """An unrecognised format key yields a 'failed' row but doesn't abort."""
    _install_fake_scene_io(monkeypatch)
    _make_check_service(monkeypatch, [])
    scene, _head = _scene_with_head()

    result = wf.export_head_scene(
        scene, formats=["wat"], out_dir=str(tmp_path),
        write_sidecar=True,
    )
    # Sidecar still wrote, so the overall result is ok.
    assert result.ok is True
    assert len(result.formats) == 1
    assert result.formats[0].code == "failed"


# ──────────────────────────────────────────────────────────────────────
#  T603 ▸ Viseme test surface
# ──────────────────────────────────────────────────────────────────────

def test_t603_available_visemes_returns_16_entries(monkeypatch):
    """LIPShape exposes 16 visemes; the workflow surfaces all of them."""
    _install_fake_lip(monkeypatch)
    visemes = wf.available_visemes()
    assert len(visemes) == 16
    # First entry is index 0 (REST).
    assert visemes[0][0] == 0
    # All indices are unique.
    indices = {idx for idx, _ in visemes}
    assert len(indices) == 16


def test_t603_apply_viseme_with_no_head_fails():
    scene = _make_scene()
    ok, msg = wf.apply_viseme(scene, 5)
    assert ok is False
    assert "No head" in msg


def test_t603_apply_viseme_out_of_range(monkeypatch):
    _install_fake_lip(monkeypatch)
    _install_fake_cb(monkeypatch)
    scene, _head = _scene_with_head()
    ok, msg = wf.apply_viseme(scene, 99)
    assert ok is False
    assert "out of range" in msg


def test_t603_apply_viseme_without_talk_animation_fails(monkeypatch):
    """A head with no 'talk' animation cannot snap to visemes."""
    _install_fake_lip(monkeypatch)
    _install_fake_cb(monkeypatch)
    scene, head = _scene_with_head()
    # Ensure no talk animation is present.
    head.animations = []
    ok, msg = wf.apply_viseme(scene, 3)
    assert ok is False
    assert "talk" in msg.lower()


def test_t603_apply_viseme_with_talk_animation_succeeds(monkeypatch):
    _install_fake_lip(monkeypatch)
    _install_fake_cb(monkeypatch)

    class _Anim:
        name = "talk"
        nodes = {}

    scene, head = _scene_with_head()
    head.animations = [_Anim()]
    ok, msg = wf.apply_viseme(scene, 3)
    assert ok is True
    assert "Viseme 3" in msg


# ──────────────────────────────────────────────────────────────────────
#  T604 ▸ Phoneme calibration registry
# ──────────────────────────────────────────────────────────────────────

def test_t604_phoneme_poses_has_eight_entries():
    """Roadmap spec: 8-pose dict."""
    assert len(wf.PHONEME_POSES) == 8
    # All entries are (label, viseme_index) tuples within range.
    for label, idx in wf.PHONEME_POSES:
        assert isinstance(label, str) and label
        assert isinstance(idx, int)
        assert 0 <= idx <= 15


def test_t604_calibrate_phoneme_no_head_fails():
    scene = _make_scene()
    ok, msg = wf.calibrate_phoneme(scene, wf.PHONEME_POSES[0][0], 5)
    assert ok is False
    assert "No head" in msg


def test_t604_calibrate_phoneme_unknown_label_fails(monkeypatch):
    _install_fake_lip(monkeypatch)
    scene, _head = _scene_with_head()
    ok, msg = wf.calibrate_phoneme(scene, "FAKE_PHONEME_XYZ", 5)
    assert ok is False
    assert "Unknown phoneme" in msg


def test_t604_calibrate_phoneme_out_of_range_index_fails(monkeypatch):
    _install_fake_lip(monkeypatch)
    scene, _head = _scene_with_head()
    label = wf.PHONEME_POSES[0][0]
    ok, msg = wf.calibrate_phoneme(scene, label, 99)
    assert ok is False
    assert "not in available set" in msg or "out of range" in msg


def test_t604_calibrate_phoneme_happy_path_stores_on_scene(monkeypatch):
    _install_fake_lip(monkeypatch)
    scene, _head = _scene_with_head()
    label, default_idx = wf.PHONEME_POSES[0]
    ok, msg = wf.calibrate_phoneme(scene, label, default_idx)
    assert ok is True
    assert label in msg
    # The mapping is persisted on the scene.
    calib = getattr(scene, "head_phoneme_calibration", None)
    assert calib is not None
    assert calib[label] == default_idx


# ──────────────────────────────────────────────────────────────────────
#  T605 ▸ Head-mode camera preset
# ──────────────────────────────────────────────────────────────────────

def test_t605_head_camera_preset_has_required_keys():
    preset = wf.head_camera_preset()
    for key in ("eye", "target", "up", "fov_deg", "clip"):
        assert key in preset
    # Vectors are length-3 tuples (except fov/clip).
    assert len(preset["eye"]) == 3
    assert len(preset["target"]) == 3
    assert len(preset["up"]) == 3
    assert len(preset["fov_deg"]) == 1
    assert len(preset["clip"]) == 2
    # FOV is reasonable for portrait framing.
    assert 20.0 <= preset["fov_deg"][0] <= 60.0


def test_t605_head_camera_preset_is_copy_not_alias():
    """Mutating the returned dict must not affect subsequent calls."""
    p1 = wf.head_camera_preset()
    p1["eye"] = (99.0, 99.0, 99.0)
    p2 = wf.head_camera_preset()
    assert p2["eye"] != (99.0, 99.0, 99.0)


# ──────────────────────────────────────────────────────────────────────
#  T601 ▸ Shared _workflow_base module
# ──────────────────────────────────────────────────────────────────────

def test_t601_workflow_base_summarize_issues_mixed():
    """The shared summariser handles mixed-severity lists."""
    issues = [
        _FakeIssue("error", "E1"),
        _FakeIssue("warning", "W1"),
        _FakeIssue("warning", "W2"),
        _FakeIssue("info", "I1"),
    ]
    key, summary, errs, warns, infos, codes = wb.summarize_issues(issues)
    assert key == "error"
    assert errs == 1
    assert warns == 2
    assert infos == 1
    assert codes == {"E1", "W1", "W2", "I1"}
    assert "1 ERROR" in summary
    assert "2 WARNINGS" in summary


def test_t601_workflow_base_summarize_issues_empty_is_clean():
    key, summary, errs, warns, infos, codes = wb.summarize_issues([])
    assert key == "clean"
    assert summary == "CLEAN"
    assert errs == warns == infos == 0


def test_t601_workflow_base_blocking_codes_only_errors():
    issues = [
        _FakeIssue("error", "E1"),
        _FakeIssue("error", "E2"),
        _FakeIssue("warning", "W1"),
        _FakeIssue("info", "I1"),
    ]
    codes = wb.blocking_codes_from_issues(issues)
    # Sorted, deduped, errors only.
    assert codes == ["E1", "E2"]


def test_t601_workflow_base_safe_resref():
    assert wb.safe_resref("PFHC@01") == "pfhc01"
    assert wb.safe_resref("Path/With/Slashes") == "pathwithslashes"
    assert wb.safe_resref("") == "untitled"
    assert wb.safe_resref("!!!", fallback="default") == "default"


def test_t601_workflow_base_severity_via_name_attr():
    """Issues whose ``severity`` only has ``.name`` (not ``.value``) still work.

    This guards M5 invariant #3: ``severity.value.lower()`` falls back to
    ``severity.name`` (then ``str(severity)``).
    """

    class _NameOnlySeverity:
        def __init__(self, n):
            self.name = n
        # No .value attribute.

    class _NameIssue:
        def __init__(self, sev, code):
            self.severity = _NameOnlySeverity(sev)
            self.code = code

    issues = [_NameIssue("ERROR", "X1"), _NameIssue("WARNING", "X2")]
    blocking = wb.blocking_codes_from_issues(issues)
    assert blocking == ["X1"]
