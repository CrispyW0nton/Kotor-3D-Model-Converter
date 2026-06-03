"""
tests/test_headless_body_workflow.py — M5 / T501-T506 workflow service tests.

Exercises the pure-Python service module ``src.core.headless_body_workflow``
in isolation from the Qt UI.  The tests construct a minimal fake
:class:`CharacterScene` + ``KotorModel`` so they run without PyKotor or
PySide6 installed.

Roadmap reference: knowledge_base/roadmap/02_roadmap_2026_05.md M5/T501-T506.
"""

from __future__ import annotations

import importlib.util as _il_util
import os
import pathlib
import sys
from types import SimpleNamespace
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
    environments.  Loading ``model_data.py`` and
    ``headless_body_workflow.py`` directly via their file paths lets
    these tests run without that dependency, matching the pattern used
    in ``tests/test_character_mode.py``.
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
        "ghostrigger_md_under_test",
        _SRC_DIR / "core" / "geometry" / "model_data.py",
    )
    wf = _load_module_direct(
        "ghostrigger_workflow_under_test",
        _SRC_DIR / "core" / "characters" / "headless_body_workflow.py",
    )
    # The workflow module's ``_import_model_data()`` helper would
    # normally pull in the full ``core`` package; rebind it to the
    # already-loaded ``md`` module so the dispatcher uses the same
    # ``PartSlot`` / ``CharacterMode`` identities as the tests.
    wf._import_model_data = lambda: md                       # type: ignore[attr-defined]
except Exception as exc:                                    # pragma: no cover
    pytest.skip(f"workflow / model_data unavailable: {exc}",
                allow_module_level=True)


# ── Test helpers ────────────────────────────────────────────────────────────
class _FakeNode:
    """Minimal stand-in for a ``ModelNode``."""

    def __init__(self, name: str, parent=None):
        self.name = name
        self.parent = parent
        self.children = []
        self.is_skin = False
        self.is_mesh = False
        self.vertices = []
        self.faces = []
        self.skin_data = []
        self.bone_map = []
        self.qbone_list = []
        self.tbone_list = []
        if parent is not None:
            parent.children.append(self)


class _FakeBodyModel:
    """A KotorModel-shaped object that detects as HEADLESS_BODY.

    Per ``detect_character_mode``:
      * classification CHARACTER
      * has ``headhook`` + ``rhand``
      * no facial bones (f_jaw_g / f_um_g / f_lmc_g / f_rmc_g)
    """

    def __init__(self, name: str = "pfbcm"):
        self.name = name
        self.supermodel = "S_Female02"
        self.model_type = int(md.ModelClassification.CHARACTER)
        self.metadata = {}
        self.metadata["character_builder_rig_state"] = {
            "state": "native_template_final",
            "dag_authority": "native_kotor_base",
            "mesh_role": "payload_guest",
            "source": "test_fake_body",
            "native_snapshot_present": True,
            "legacy_acurig": False,
        }
        self._gr_character_builder_rig_state = dict(self.metadata["character_builder_rig_state"])
        self.root_node = _FakeNode(name)
        rootdummy = _FakeNode("rootdummy", self.root_node)
        headhook = _FakeNode("headhook", rootdummy)
        rhand = _FakeNode("rhand", rootdummy)
        lhand = _FakeNode("lhand", rootdummy)
        skin = _FakeNode("custom_body", self.root_node)
        skin.is_skin = True
        skin.vertices = [(0.0, 0.0, 0.0)]
        skin.faces = [(0, 0, 0)]
        skin.bone_map = [rootdummy]
        skin.qbone_list = [rootdummy]
        skin.tbone_list = [rootdummy]
        skin.skin_data = [
            SimpleNamespace(
                influences=[
                    SimpleNamespace(bone_index=0, weight=1.0),
                ]
            )
        ]
        self._nodes = [
            self.root_node,
            rootdummy,
            headhook,
            rhand,
            lhand,
            skin,
        ]
        self._gr_native_skeleton_snapshot = SimpleNamespace(
            model_name=name,
            game="K1",
            supermodel="S_Female02",
            metadata={"source_resref": name, "source_game": "K1"},
            nodes=[
                SimpleNamespace(
                    name=name,
                    full_path=(name,),
                    export_role="helper",
                    socket_category=None,
                ),
                SimpleNamespace(
                    name="rootdummy",
                    full_path=(name, "rootdummy"),
                    export_role="helper",
                    socket_category=None,
                ),
                SimpleNamespace(
                    name="headhook",
                    full_path=(name, "rootdummy", "headhook"),
                    export_role="socket",
                    socket_category="head",
                ),
                SimpleNamespace(
                    name="rhand",
                    full_path=(name, "rootdummy", "rhand"),
                    export_role="socket",
                    socket_category="right_hand",
                ),
                SimpleNamespace(
                    name="lhand",
                    full_path=(name, "rootdummy", "lhand"),
                    export_role="socket",
                    socket_category="left_hand",
                ),
            ],
        )

    def all_nodes(self):
        return list(self._nodes)


class _FakeHeadModel:
    """KotorModel-shaped object that detects as HEAD."""

    def __init__(self, name: str = "pfhc01"):
        self.name = name
        self.supermodel = "S_Female02"
        self.model_type = int(md.ModelClassification.CHARACTER)
        self._nodes = [
            _FakeNode("rootdummy"),
            _FakeNode("head_g"),
            _FakeNode("talkdummy"),
            _FakeNode("f_jaw_g"),
            _FakeNode("f_um_g"),
            _FakeNode("f_lmc_g"),
            _FakeNode("f_rmc_g"),
        ]

    def all_nodes(self):
        return list(self._nodes)


class _FakeAmbiguousExternalModel:
    """External mesh before a KOTOR base skeleton has been applied."""

    def __init__(self, name: str = "bendak"):
        self.name = name
        self.supermodel = "NULL"
        self.model_type = int(md.ModelClassification.CHARACTER)
        self._nodes = [
            _FakeNode("bendak"),
        ]

    def all_nodes(self):
        return list(self._nodes)


class _FakeTexturedSkinModel:
    """External skinned mesh with a Blender-style material texture stem."""

    def __init__(self, texture: str = "BendakStarkiller_basecolor"):
        self.name = "bendak"
        skin = _FakeNode("Bendak")
        skin.is_skin = True
        skin.is_mesh = False
        skin.texture = texture
        skin.texture_names = []
        skin.vertices = [(0.0, 0.0, 0.0)]
        self._nodes = [skin]

    def all_nodes(self):
        return list(self._nodes)


class _FakeExternalMeshModel:
    """Minimal external mesh with a non-KOTOR source scale."""

    def __init__(self, vertices):
        self.name = "external"
        self.metadata = {}
        mesh = _FakeNode("mesh")
        mesh.is_mesh = True
        mesh.is_skin = False
        mesh.vertices = list(vertices)
        mesh.normals = [(0.0, 0.0, 1.0) for _ in mesh.vertices]
        self._nodes = [mesh]
        self.root_node = mesh
        self.compute_bounds()

    def all_nodes(self):
        return list(self._nodes)

    def compute_bounds(self):
        verts = self._nodes[0].vertices
        self.bb_min = tuple(min(v[i] for v in verts) for i in range(3))
        self.bb_max = tuple(max(v[i] for v in verts) for i in range(3))


def _make_scene(game_version: str = "K1"):
    return md.CharacterScene(game_version=game_version)


# ── T501 ▸ supported_load_extensions / load_file_filter ─────────────────────
def test_t501_supported_extensions_cover_spec():
    """Roadmap spec: MDL/MDX/OBJ/FBX/glTF; UTC bonus per T501 wording."""
    exts = wf.supported_load_extensions()
    for needed in (".mdl", ".gltf", ".glb", ".fbx", ".obj", ".utc"):
        assert needed in exts, f"missing extension: {needed}"


def test_t501_load_file_filter_format():
    """Filter string must follow Qt's ``"Label (*.x *.y);;All files (*.*)"``."""
    f = wf.load_file_filter()
    assert "Body models" in f
    assert "*.mdl" in f
    assert "*.gltf" in f
    assert ";;All files (*.*)" in f


# ── T501 ▸ Defensive parameter handling ─────────────────────────────────────
def test_t501_load_body_empty_path_returns_structured_error():
    scene = _make_scene()
    result = wf.load_body("", scene)
    assert result.ok is False
    assert result.code == "empty_path"
    assert "no file path" in result.message.lower() or "path" in result.message.lower()
    # Scene must not have been mutated.
    assert md.PartSlot.HEADLESS_BODY not in scene.slots


def test_t501_load_body_missing_file_returns_file_not_found():
    scene = _make_scene()
    result = wf.load_body("/tmp/does_not_exist_qt_ghostrigger.mdl", scene)
    assert result.ok is False
    assert result.code == "file_not_found"
    assert md.PartSlot.HEADLESS_BODY not in scene.slots


def test_t501_load_body_unsupported_extension_is_rejected(tmp_path):
    scene = _make_scene()
    junk = tmp_path / "model.xyz"
    junk.write_bytes(b"not a model")
    result = wf.load_body(str(junk), scene)
    assert result.ok is False
    assert result.code == "unsupported_format"
    assert md.PartSlot.HEADLESS_BODY not in scene.slots


# ── T501 ▸ Happy-path mocked loader ─────────────────────────────────────────
def test_t501_load_body_happy_path_assigns_slot(tmp_path, monkeypatch):
    """When a body MDL loads cleanly, ``load_body`` mutates the scene."""
    fake = _FakeBodyModel("pfbcm")
    mdl_path = tmp_path / "pfbcm.mdl"
    mdl_path.write_bytes(b"stub mdl bytes")
    # Intercept the MDL loader inside the workflow module so we never
    # touch the real PyKotor path.
    monkeypatch.setattr(wf, "_load_mdl", lambda path, gv: fake)

    scene = _make_scene("K1")
    result = wf.load_body(str(mdl_path), scene)

    assert result.ok is True
    assert result.code == "loaded"
    assert result.model is fake
    assert result.detected_mode == md.CharacterMode.HEADLESS_BODY
    assert result.resref == "pfbcm"
    # Slot must be assigned with the right resref + source_path.
    entry = scene.get(md.PartSlot.HEADLESS_BODY)
    assert entry is not None
    assert entry.model is fake
    assert entry.resref == "pfbcm"
    assert entry.source_path == str(mdl_path)
    assert entry.game_version == "K1"


def test_t501_load_body_mode_mismatch_returns_warning_not_error(tmp_path, monkeypatch):
    """Loading a HEAD model into the body workflow surfaces a warning, not an error."""
    fake = _FakeHeadModel("pfhc01")
    mdl_path = tmp_path / "pfhc01.mdl"
    mdl_path.write_bytes(b"stub mdl bytes")
    monkeypatch.setattr(wf, "_load_mdl", lambda path, gv: fake)

    scene = _make_scene("K1")
    result = wf.load_body(str(mdl_path), scene)

    assert result.code == "mode_mismatch"
    assert result.ok is False           # caller hasn't opted into correction
    assert result.detected_mode == md.CharacterMode.HEAD
    # Slot is still assigned so the user can see what they loaded.
    entry = scene.get(md.PartSlot.HEADLESS_BODY)
    assert entry is not None
    assert entry.model is fake


def test_t501_load_body_mode_correction_flag_promotes_to_ok(tmp_path, monkeypatch):
    """``allow_mode_correction=True`` flips a mode-mismatch into a success."""
    fake = _FakeHeadModel("pfhc01")
    mdl_path = tmp_path / "pfhc01.mdl"
    mdl_path.write_bytes(b"stub mdl bytes")
    monkeypatch.setattr(wf, "_load_mdl", lambda path, gv: fake)

    scene = _make_scene("K1")
    result = wf.load_body(str(mdl_path), scene, allow_mode_correction=True)

    assert result.ok is True
    assert result.code == "loaded"
    assert result.detected_mode == md.CharacterMode.HEAD


def test_t501_load_body_loader_failure_returns_load_failed(tmp_path, monkeypatch):
    """When the underlying importer returns None, we report ``load_failed``."""
    mdl_path = tmp_path / "broken.mdl"
    mdl_path.write_bytes(b"\x00")
    monkeypatch.setattr(wf, "_load_mdl", lambda path, gv: None)

    scene = _make_scene("K1")
    result = wf.load_body(str(mdl_path), scene)

    assert result.ok is False
    assert result.code == "load_failed"
    assert md.PartSlot.HEADLESS_BODY not in scene.slots


def test_t501_load_body_uses_scene_game_version_by_default(tmp_path, monkeypatch):
    fake = _FakeBodyModel("k2body")
    mdl_path = tmp_path / "k2body.mdl"
    mdl_path.write_bytes(b"stub")
    seen: List[str] = []
    monkeypatch.setattr(wf, "_load_mdl",
                        lambda path, gv: (seen.append(gv) or fake))

    scene = _make_scene("K2")
    wf.load_body(str(mdl_path), scene)
    assert seen == ["K2"]
    entry = scene.get(md.PartSlot.HEADLESS_BODY)
    assert entry.game_version == "K2"


def test_t501_load_body_dispatches_gltf_to_auto_importer(tmp_path, monkeypatch):
    fake = _FakeBodyModel("body_from_gltf")
    glb = tmp_path / "body_from_gltf.glb"
    glb.write_bytes(b"glb stub")
    called: List[str] = []
    monkeypatch.setattr(wf, "_load_gltf_or_mesh",
                        lambda path, gv: (called.append(path) or fake))
    monkeypatch.setattr(wf, "_load_mdl",
                        lambda *a, **kw: pytest.fail("MDL loader should not run"))

    scene = _make_scene("K1")
    result = wf.load_body(str(glb), scene)
    assert called == [str(glb)]
    assert result.ok is True


def test_t501_load_body_accepts_ambiguous_external_mesh_for_template_flow(
    tmp_path,
    monkeypatch,
):
    fake = _FakeAmbiguousExternalModel("bendak")
    fbx = tmp_path / "Bendak.fbx"
    fbx.write_bytes(b"fbx stub")
    monkeypatch.setattr(wf, "_load_gltf_or_mesh", lambda path, gv: fake)

    scene = _make_scene("K1")
    result = wf.load_body(str(fbx), scene)

    assert result.ok is True
    assert result.code == "loaded"
    assert result.detected_mode == md.CharacterMode.AMBIGUOUS
    assert "KOTOR base skeleton" in result.message
    assert scene.get(md.PartSlot.HEADLESS_BODY).resref == "bendak"


def test_t501_load_body_resref_is_lowercase_basename(tmp_path, monkeypatch):
    fake = _FakeBodyModel("PFBCM")
    p = tmp_path / "PFBCM_v2.mdl"
    p.write_bytes(b"x")
    monkeypatch.setattr(wf, "_load_mdl", lambda path, gv: fake)
    scene = _make_scene()
    result = wf.load_body(str(p), scene)
    assert result.resref == "pfbcm_v2"
    assert scene.get(md.PartSlot.HEADLESS_BODY).resref == "pfbcm_v2"


def test_t501_load_body_utc_without_library_returns_structured_failure(tmp_path):
    """UTC path without a configured installation returns a clean
    ``load_failed`` so the UI can fall back to a direct MDL picker."""
    utc = tmp_path / "p_revan.utc"
    utc.write_bytes(b"GFF UTC stub")
    scene = _make_scene()
    result = wf.load_body(str(utc), scene)
    assert result.ok is False
    assert result.code == "load_failed"
    assert "KOTOR installation" in result.message
    assert md.PartSlot.HEADLESS_BODY not in scene.slots


# ── T502 ▸ Check-Model summarizer ───────────────────────────────────────────
class _FakeSeverity:
    def __init__(self, value: str):
        self.value = value


class _FakeIssue:
    """Duck-typed ValidationIssue for testing the summarizer."""

    def __init__(self, severity: str, code: str, slot=None,
                 node: str = "", message: str = ""):
        self.severity = _FakeSeverity(severity)
        self.code = code
        self.slot = slot
        self.node = node
        self.message = message


def _make_check_service(monkeypatch, issues: List[Any]):
    """Stub the ValidationService so :func:`check_model` returns the
    given canned issue list without touching the heavy validator."""
    class _StubService:
        def __init__(self, scene, *, strict: bool = False, **kw):
            self.scene = scene
            self.strict = strict

        def validate(self):
            return list(issues)

    class _StubMod:
        ValidationService = _StubService

    monkeypatch.setattr(wf, "_import_validation_service", lambda: _StubMod)


def test_t502_check_model_empty_scene_returns_no_model_loaded():
    """An unpopulated scene must not be reported as 'clean'."""
    scene = _make_scene()
    result = wf.check_model(scene)
    assert result.ok is False
    assert result.banner_key == "warning"
    assert "NO MODEL" in result.summary.upper()


def test_t502_check_model_clean_scene(monkeypatch):
    """Validator returns no issues → banner is CLEAN."""
    _make_check_service(monkeypatch, [])
    scene = _make_scene()
    # Populate slot so the early-out doesn't fire.
    scene.assign(md.PartSlot.HEADLESS_BODY, _FakeBodyModel("body"),
                 resref="body", source_path="x")
    result = wf.check_model(scene)
    assert result.ok is True
    assert result.banner_key == "clean"
    assert result.summary == "CLEAN"
    assert result.error_count == result.warning_count == result.info_count == 0


def test_t502_check_model_aggregates_error_warning_info(monkeypatch):
    """Mixed severities must produce an error-key banner with full tally."""
    issues = [
        _FakeIssue("error",   "HOOK_MISSING",       message="no headhook"),
        _FakeIssue("error",   "K1_K2_MISMATCH",     message="games disagree"),
        _FakeIssue("warning", "SUPERMODEL_UNKNOWN", message="not in K1 set"),
        _FakeIssue("warning", "WEIGHT_OVERFLOW",    message=">4 influences"),
        _FakeIssue("warning", "BONE_MISSING",       message="no lshoulder"),
        _FakeIssue("info",    "WEIGHT_ERRORS_TRUNCATED",
                   message="capped at 20"),
    ]
    _make_check_service(monkeypatch, issues)
    scene = _make_scene()
    scene.assign(md.PartSlot.HEADLESS_BODY, _FakeBodyModel("body"),
                 resref="body", source_path="x")
    result = wf.check_model(scene)
    assert result.banner_key == "error"
    assert result.error_count == 2
    assert result.warning_count == 3
    assert result.info_count == 1
    assert result.ok is False                # has errors
    assert result.summary == "2 ERRORS, 3 WARNINGS"


def test_t502_check_model_warning_only_yields_warning_banner(monkeypatch):
    _make_check_service(monkeypatch, [
        _FakeIssue("warning", "WEIGHT_ZERO_SUM", message="sum=0"),
    ])
    scene = _make_scene()
    scene.assign(md.PartSlot.HEADLESS_BODY, _FakeBodyModel("body"),
                 resref="body", source_path="x")
    result = wf.check_model(scene)
    assert result.banner_key == "warning"
    assert result.ok is True                 # warnings don't block
    assert result.summary == "1 WARNING"


def test_t502_check_model_info_only_yields_info_banner(monkeypatch):
    _make_check_service(monkeypatch, [
        _FakeIssue("info", "WEIGHT_ERRORS_TRUNCATED",
                   message="20 weight errors not shown"),
    ])
    scene = _make_scene()
    scene.assign(md.PartSlot.HEADLESS_BODY, _FakeBodyModel("body"),
                 resref="body", source_path="x")
    result = wf.check_model(scene)
    assert result.banner_key == "info"
    assert result.ok is True
    assert result.summary == "1 INFO"


def test_t502_check_model_all_ten_codes_surface(monkeypatch):
    """Acceptance: ``All 10 issue codes surface correctly``.

    Feeds one instance of every documented validator code and asserts
    that ``result.codes`` contains every one of them.
    """
    canonical_codes = [
        "NO_GEOMETRY",
        "K1_K2_MISMATCH",
        "SUPERMODEL_MISMATCH",
        "SUPERMODEL_UNKNOWN",
        "HOOK_MISSING",
        "BONE_MISSING",
        "SKIN_MESH_UNRIGGED",
        "WEIGHT_OVERFLOW",
        "WEIGHT_ZERO_SUM",
        "WEIGHT_UNNORMALIZED",
    ]
    _make_check_service(monkeypatch, [
        _FakeIssue("error" if c.endswith("MISMATCH") else "warning",
                   c, message=f"issue {c}")
        for c in canonical_codes
    ])
    scene = _make_scene()
    scene.assign(md.PartSlot.HEADLESS_BODY, _FakeBodyModel("body"),
                 resref="body", source_path="x")
    result = wf.check_model(scene)
    assert result.codes == set(canonical_codes), \
        f"missing codes: {set(canonical_codes) - result.codes}"


def test_t502_check_model_service_failure_returns_error_banner(monkeypatch):
    """If ValidationService raises, the result must still be banner-ready."""
    class _BrokenService:
        def __init__(self, scene, **kw):
            raise RuntimeError("validator deps missing")

    class _BrokenMod:
        ValidationService = _BrokenService

    monkeypatch.setattr(wf, "_import_validation_service", lambda: _BrokenMod)

    scene = _make_scene()
    scene.assign(md.PartSlot.HEADLESS_BODY, _FakeBodyModel("body"),
                 resref="body", source_path="x")
    result = wf.check_model(scene)
    assert result.banner_key == "error"
    assert result.ok is False
    assert "CHECK FAILED" in result.summary


def test_t502_check_model_strict_passes_through_to_service(monkeypatch):
    """The ``strict`` keyword must reach the underlying ValidationService."""
    captured: dict = {}

    class _RecordingService:
        def __init__(self, scene, *, strict: bool = False, **kw):
            captured["strict"] = strict

        def validate(self):
            return []

    class _Mod:
        ValidationService = _RecordingService

    monkeypatch.setattr(wf, "_import_validation_service", lambda: _Mod)
    scene = _make_scene()
    scene.assign(md.PartSlot.HEADLESS_BODY, _FakeBodyModel("body"),
                 resref="body", source_path="x")
    wf.check_model(scene, strict=True)
    assert captured["strict"] is True


# ── T503 ▸ place_body_guides / generate_skeleton ────────────────────────────
class _FakeGuide:
    """Minimal stand-in for ``accurig.RigGuide``."""

    def __init__(self, name, position=(0.0, 0.0, 0.0), locked=False):
        self.name = name
        self.position = position
        self.locked = locked


class _FakeAcuRig:
    """Records calls + emits deterministic guides / rigged-model output.

    Used in place of :class:`accurig.AcuRig` so the workflow tests stay
    fully Qt-free and PyKotor-free.
    """

    PROFILE_HUMANOID = "humanoid"

    def __init__(self):
        self.place_calls: list = []
        self.generate_calls: list = []
        self.skin_calls: list = []
        # Default guide map mirrors the canonical humanoid layout.
        self._guides = {
            name: _FakeGuide(name)
            for name in ("root", "hip", "chest",
                         "lshoulder", "lforearm", "lhand",
                         "rshoulder", "rforearm", "rhand")
        }
        self._rigged_model = None
        self._verts_to_return = 1234
        # Raise hooks — set by individual tests.
        self.place_raises: Exception | None = None
        self.generate_raises: Exception | None = None
        self.skin_raises: Exception | None = None

    def move_guide(self, name, position, auto_mirror=True):
        key = str(name).lower()
        if key not in self._guides:
            self._guides[key] = _FakeGuide(key, position, locked=True)
        else:
            self._guides[key].position = position
            self._guides[key].locked = True
        if auto_mirror and key.startswith("l"):
            partner = "r" + key[1:]
            if partner in self._guides and not self._guides[partner].locked:
                x, y, z = position
                self._guides[partner].position = (-x, y, z)

    def place_guides(self, model, *, profile=None, snap_to_bones=True):
        self.place_calls.append({
            "model": model,
            "profile": profile,
            "snap_to_bones": snap_to_bones,
        })
        if self.place_raises is not None:
            raise self.place_raises
        return dict(self._guides)

    def get_all_guides(self):
        return dict(self._guides)

    def generate_rig(self, model, *, guides=None):
        self.generate_calls.append({"model": model, "guides": guides})
        if self.generate_raises is not None:
            raise self.generate_raises
        # Mimic AcuRig: returns a rigged model (may equal the input).
        rigged = self._rigged_model if self._rigged_model is not None else model
        return rigged

    def auto_skin(self, model, *, guides=None, smooth_iterations=2):
        self.skin_calls.append({
            "model": model,
            "guides": guides,
            "smooth_iterations": smooth_iterations,
        })
        if self.skin_raises is not None:
            raise self.skin_raises
        return self._verts_to_return


def _install_fake_accurig(monkeypatch):
    """Rebind ``wf._import_accurig`` to a deterministic fake module.

    Returns the :class:`_FakeAcuRig` instance the workflow will use, so
    individual tests can pre-program ``place_raises`` / ``skin_raises``
    / ``_rigged_model`` / ``_verts_to_return`` before invoking the
    public functions.
    """
    fake = _FakeAcuRig()

    class _Mod:
        PROFILE_HUMANOID = "humanoid"
        # Factory: the workflow calls ``ar_mod.AcuRig()`` when no
        # instance is passed; return the same fake every time so tests
        # can assert against a single object.
        AcuRig = staticmethod(lambda: fake)

    monkeypatch.setattr(wf, "_import_accurig", lambda: _Mod)
    return fake


def _scene_with_body(name: str = "pfbcm"):
    scene = _make_scene("K1")
    body = _FakeBodyModel(name)
    scene.assign(md.PartSlot.HEADLESS_BODY, body,
                 resref=name, source_path=f"/tmp/{name}.mdl")
    return scene, body


# ── T503 ▸ place_body_guides ───────────────────────────────────────────────
def test_t503_place_body_guides_no_body_returns_structured_error(monkeypatch):
    """When the body slot is empty, ``place_body_guides`` reports it cleanly."""
    fake = _install_fake_accurig(monkeypatch)
    scene = _make_scene("K1")  # no body assigned

    result = wf.place_body_guides(scene)

    assert result.ok is False
    assert result.guides == {}
    assert result.acurig is None
    assert "no body" in result.message.lower() or "load a body" in result.message.lower()
    # The fake must not have been invoked.
    assert fake.place_calls == []


def test_t503_place_body_guides_happy_path_returns_guides_and_instance(monkeypatch):
    """The happy path returns the AcuRig instance + populated guide map."""
    fake = _install_fake_accurig(monkeypatch)
    scene, body = _scene_with_body("pfbcm")

    result = wf.place_body_guides(scene, snap_to_bones=True)

    assert result.ok is True
    assert result.profile == "humanoid"
    assert result.acurig is fake
    assert set(result.guides.keys()) >= {"root", "hip", "chest",
                                         "lshoulder", "rshoulder",
                                         "lhand", "rhand"}
    # AcuRig.place_guides was called with the body + correct kwargs.
    assert len(fake.place_calls) == 1
    call = fake.place_calls[0]
    assert call["model"] is body
    assert call["profile"] == "humanoid"
    assert call["snap_to_bones"] is True
    # Status message is non-empty + mentions the guide count.
    assert str(len(result.guides)) in result.message


def test_t503_place_body_guides_snap_kwarg_is_forwarded(monkeypatch):
    """``snap_to_bones=False`` must reach AcuRig.place_guides verbatim."""
    fake = _install_fake_accurig(monkeypatch)
    scene, _body = _scene_with_body()

    wf.place_body_guides(scene, snap_to_bones=False)

    assert fake.place_calls[0]["snap_to_bones"] is False


def test_t503_place_body_guides_reuses_caller_provided_instance(monkeypatch):
    """When ``acurig=`` is supplied, the workflow must not allocate a fresh one."""
    # Install a fake module so PROFILE_HUMANOID resolves.
    _install_fake_accurig(monkeypatch)
    # Caller-supplied instance — different identity from the module's factory.
    caller = _FakeAcuRig()
    scene, _body = _scene_with_body()

    result = wf.place_body_guides(scene, acurig=caller)

    assert result.ok is True
    assert result.acurig is caller
    assert len(caller.place_calls) == 1


def test_t503_place_body_guides_acurig_raise_is_swallowed_as_failure(monkeypatch):
    """When AcuRig.place_guides raises, the workflow returns ok=False, not bubbles."""
    fake = _install_fake_accurig(monkeypatch)
    fake.place_raises = RuntimeError("snap radius too small")
    scene, _body = _scene_with_body()

    result = wf.place_body_guides(scene)

    assert result.ok is False
    assert result.guides == {}
    assert "snap radius too small" in result.message


# ── T503 ▸ generate_skeleton ───────────────────────────────────────────────
def test_t503_generate_skeleton_no_body_returns_structured_error(monkeypatch):
    """Empty body slot → ``no_body`` code, no AcuRig call."""
    fake = _install_fake_accurig(monkeypatch)
    scene = _make_scene("K1")

    result = wf.generate_skeleton(scene)

    assert result.ok is False
    assert result.code == "no_body"
    assert result.bone_count == 0
    assert fake.generate_calls == []
    assert fake.skin_calls == []


def test_t503_generate_skeleton_happy_path_returns_counts(monkeypatch):
    """Full happy path: build + skin succeed, counts surface on result."""
    fake = _install_fake_accurig(monkeypatch)
    rigged = _FakeBodyModel("pfbcm_rigged")
    fake._rigged_model = rigged
    fake._verts_to_return = 4567
    scene, body = _scene_with_body("pfbcm")

    result = wf.generate_skeleton(scene, smooth_iterations=3)

    assert result.ok is True
    assert result.code == "generated"
    assert result.bone_count == len(fake._guides)  # 9 in the fake map
    assert result.vertices_skinned == 4567
    # generate_rig + auto_skin both received the right inputs.
    assert len(fake.generate_calls) == 1
    assert fake.generate_calls[0]["model"] is body
    assert len(fake.skin_calls) == 1
    assert fake.skin_calls[0]["model"] is rigged
    assert fake.skin_calls[0]["smooth_iterations"] == 3


def test_t503_generate_skeleton_replaces_scene_slot_model(monkeypatch):
    """The rigged model returned by generate_rig must overwrite slot.model."""
    fake = _install_fake_accurig(monkeypatch)
    rigged = _FakeBodyModel("pfbcm_rigged")
    fake._rigged_model = rigged
    scene, body = _scene_with_body("pfbcm")

    result = wf.generate_skeleton(scene)

    assert result.ok is True
    entry = scene.get(md.PartSlot.HEADLESS_BODY)
    assert entry is not None
    assert entry.model is rigged
    assert entry.model is not body
    assert scene.dirty is True


def test_t503_generate_skeleton_reuses_caller_acurig_instance(monkeypatch):
    """A caller-supplied AcuRig instance must be used directly (no fresh alloc)."""
    _install_fake_accurig(monkeypatch)
    caller = _FakeAcuRig()
    scene, _body = _scene_with_body()
    # Pre-seed the caller's guide map so we can assert it's used.
    caller._guides = {"root": _FakeGuide("root"),
                      "hip": _FakeGuide("hip"),
                      "chest": _FakeGuide("chest")}

    result = wf.generate_skeleton(scene, acurig=caller)

    assert result.ok is True
    # generate_rig + auto_skin were called on the *caller's* instance.
    assert len(caller.generate_calls) == 1
    assert len(caller.skin_calls) == 1
    # When no explicit guides arg is passed, the workflow forwards
    # ``guides=None`` to generate_rig and falls back to get_all_guides
    # for the bone count — so we should see the caller's 3-guide map.
    assert result.bone_count == 3


def test_t503_generate_skeleton_explicit_guides_kwarg_is_forwarded(monkeypatch):
    """Explicit ``guides=`` dict must reach generate_rig + auto_skin verbatim."""
    fake = _install_fake_accurig(monkeypatch)
    scene, _body = _scene_with_body()
    custom = {
        "root": _FakeGuide("root"),
        "hip":  _FakeGuide("hip"),
    }

    result = wf.generate_skeleton(scene, guides=custom)

    assert result.ok is True
    assert fake.generate_calls[0]["guides"] is custom
    assert fake.skin_calls[0]["guides"] is custom
    # Bone count comes from the explicit map, not get_all_guides.
    assert result.bone_count == 2


def test_t503_generate_skeleton_build_failure_yields_build_failed_code(monkeypatch):
    """When generate_rig raises, status code must be ``build_failed``."""
    fake = _install_fake_accurig(monkeypatch)
    fake.generate_raises = RuntimeError("hierarchy cycle detected")
    scene, _body = _scene_with_body()

    result = wf.generate_skeleton(scene)

    assert result.ok is False
    assert result.code == "build_failed"
    assert "hierarchy cycle detected" in result.message
    # auto_skin must not have been attempted.
    assert fake.skin_calls == []


def test_t503_generate_skeleton_skin_failure_yields_skin_failed_code(monkeypatch):
    """When auto_skin raises, status code must be ``skin_failed`` + bone_count preserved."""
    fake = _install_fake_accurig(monkeypatch)
    fake.skin_raises = RuntimeError("weight matrix singular")
    scene, _body = _scene_with_body()

    result = wf.generate_skeleton(scene)

    assert result.ok is False
    assert result.code == "skin_failed"
    assert result.bone_count == len(fake._guides)  # build succeeded → count known
    assert "weight matrix singular" in result.message


def test_t503_generate_skeleton_smooth_iterations_defaults_to_two(monkeypatch):
    """When the caller omits smooth_iterations, the default of 2 reaches auto_skin."""
    fake = _install_fake_accurig(monkeypatch)
    scene, _body = _scene_with_body()

    wf.generate_skeleton(scene)

    assert fake.skin_calls[0]["smooth_iterations"] == 2


# ── T1203 ▸ manual guide override persistence ──────────────────────────────
def test_t1203_update_body_guide_requires_acurig():
    result = wf.update_body_guide(None, "lhand", (1, 2, 3))

    assert result.ok is False
    assert result.code == "no_acurig"


def test_t1203_update_body_guide_locks_existing_guide(monkeypatch):
    fake = _install_fake_accurig(monkeypatch)

    result = wf.update_body_guide(fake, "lhand", (1.25, 2.5, 3.75))

    assert result.ok is True
    assert result.code == "updated"
    assert result.guide_name == "lhand"
    assert fake._guides["lhand"].position == (1.25, 2.5, 3.75)
    assert fake._guides["lhand"].locked is True
    assert "lhand" in result.updated_guides


def test_t1203_update_body_guide_rejects_unknown_nodes(monkeypatch):
    fake = _install_fake_accurig(monkeypatch)

    result = wf.update_body_guide(fake, "random_mesh", (1, 2, 3))

    assert result.ok is False
    assert result.code == "unknown_guide"
    assert "random_mesh" in result.message


def test_t1203_update_body_guide_from_node_reads_name_and_position(monkeypatch):
    fake = _install_fake_accurig(monkeypatch)

    class _Node:
        name = "hip"
        position = (0.0, 0.5, 1.0)

    result = wf.update_body_guide_from_node(fake, _Node())

    assert result.ok is True
    assert result.guide_name == "hip"
    assert fake._guides["hip"].position == (0.0, 0.5, 1.0)


def test_t1203_update_body_guide_can_auto_mirror_when_requested(monkeypatch):
    fake = _install_fake_accurig(monkeypatch)

    result = wf.update_body_guide(fake, "lhand", (-0.8, 0.1, 0.2),
                                  auto_mirror=True)

    assert result.ok is True
    assert fake._guides["rhand"].position == (0.8, 0.1, 0.2)
    assert {"lhand", "rhand"}.issubset(set(result.updated_guides))


def test_t1203_update_body_guide_captures_undo_redo_positions(monkeypatch):
    fake = _install_fake_accurig(monkeypatch)

    result = wf.update_body_guide(fake, "lhand", (1.0, 2.0, 3.0))

    assert result.before_positions["lhand"] == (0.0, 0.0, 0.0)
    assert result.after_positions["lhand"] == (1.0, 2.0, 3.0)


def test_t1203_body_guide_history_records_undo_and_redo(monkeypatch):
    fake = _install_fake_accurig(monkeypatch)
    history = wf.BodyGuideEditHistory()
    edit = wf.update_body_guide(fake, "lhand", (1.0, 2.0, 3.0))

    wf.record_body_guide_edit(history, edit)
    undo = wf.undo_body_guide_edit(fake, history)
    redo = wf.redo_body_guide_edit(fake, history)

    assert undo.ok is True
    assert undo.code == "undone"
    assert fake._guides["lhand"].position == (1.0, 2.0, 3.0)
    assert redo.ok is True
    assert redo.code == "redone"
    assert fake._guides["lhand"].position == (1.0, 2.0, 3.0)


def test_t1203_body_guide_undo_restores_previous_position(monkeypatch):
    fake = _install_fake_accurig(monkeypatch)
    history = wf.BodyGuideEditHistory()
    edit = wf.update_body_guide(fake, "lhand", (1.0, 2.0, 3.0))
    wf.record_body_guide_edit(history, edit)

    result = wf.undo_body_guide_edit(fake, history)

    assert result.ok is True
    assert fake._guides["lhand"].position == (0.0, 0.0, 0.0)
    assert history.can_undo is False
    assert history.can_redo is True


def test_t1203_body_guide_redo_reapplies_position(monkeypatch):
    fake = _install_fake_accurig(monkeypatch)
    history = wf.BodyGuideEditHistory()
    edit = wf.update_body_guide(fake, "lhand", (1.0, 2.0, 3.0))
    wf.record_body_guide_edit(history, edit)
    wf.undo_body_guide_edit(fake, history)

    result = wf.redo_body_guide_edit(fake, history)

    assert result.ok is True
    assert fake._guides["lhand"].position == (1.0, 2.0, 3.0)
    assert history.can_undo is True
    assert history.can_redo is False


def test_t1203_body_guide_undo_empty_stack_is_structured(monkeypatch):
    fake = _install_fake_accurig(monkeypatch)

    result = wf.undo_body_guide_edit(fake, wf.BodyGuideEditHistory())

    assert result.ok is False
    assert result.code == "no_undo"


# ── T504 ▸ place_hand_guides / apply_hand_masks ────────────────────────────
class _FakeBoneMask:
    """Stand-in for :class:`accurig.BoneMask` — enough surface for T504."""

    def __init__(self):
        self._masked: set = set()
        # Track raise hooks per-method so tests can assert error paths.
        self.mask_raises: Exception | None = None

    def mask(self, name: str) -> None:
        if self.mask_raises is not None:
            raise self.mask_raises
        self._masked.add(name)

    def unmask(self, name: str) -> None:
        self._masked.discard(name)

    def is_masked(self, name: str) -> bool:
        return name in self._masked

    def clear(self) -> None:
        self._masked.clear()

    @property
    def masked_bones(self):
        return sorted(self._masked)


def _install_fake_accurig_with_mask(monkeypatch):
    """Like :func:`_install_fake_accurig` but attaches a BoneMask too."""
    fake = _FakeAcuRig()
    fake.mask = _FakeBoneMask()                              # type: ignore[attr-defined]

    class _Mod:
        PROFILE_HUMANOID = "humanoid"
        AcuRig = staticmethod(lambda: fake)

    monkeypatch.setattr(wf, "_import_accurig", lambda: _Mod)
    return fake


# ── T504 ▸ place_hand_guides ───────────────────────────────────────────────
def test_t504_hand_bones_constant_covers_six_bones():
    """The exported HAND_BONES tuple must include both forearms, wrists, fingers."""
    assert set(wf.HAND_BONES) == {
        "lforearm", "lhand", "lfinger01",
        "rforearm", "rhand", "rfinger01",
    }


def test_t504_place_hand_guides_no_body_returns_structured_error(monkeypatch):
    """Empty body slot → ``no_body`` code; AcuRig must not be invoked."""
    fake = _install_fake_accurig_with_mask(monkeypatch)
    scene = _make_scene("K1")

    result = wf.place_hand_guides(scene)

    assert result.ok is False
    assert result.code == "no_body"
    assert result.guides == {}
    assert fake.place_calls == []


def test_t504_place_hand_guides_filters_to_hand_subset(monkeypatch):
    """The happy path returns only the six hand bones, even though
    AcuRig.place_guides emits the full humanoid skeleton.
    """
    fake = _install_fake_accurig_with_mask(monkeypatch)
    # Inject the full humanoid set so the workflow has to filter.
    fake._guides = {
        name: _FakeGuide(name)
        for name in ("root", "hip", "chest",
                     "lshoulder", "lforearm", "lhand", "lfinger01",
                     "rshoulder", "rforearm", "rhand", "rfinger01",
                     "lthigh", "rthigh")
    }
    scene, body = _scene_with_body("pfbcm")

    result = wf.place_hand_guides(scene)

    assert result.ok is True
    assert result.code == "placed"
    assert set(result.guides.keys()) == set(wf.HAND_BONES)
    # AcuRig was called with the body + humanoid profile.
    assert len(fake.place_calls) == 1
    assert fake.place_calls[0]["model"] is body
    assert fake.place_calls[0]["profile"] == "humanoid"
    # No bones masked yet → empty list.
    assert result.masked_bones == []
    assert result.acurig is fake


def test_t504_place_hand_guides_surfaces_existing_mask_state(monkeypatch):
    """Pre-existing mask state on the AcuRig instance must round-trip
    through ``HandRigResult.masked_bones``."""
    fake = _install_fake_accurig_with_mask(monkeypatch)
    fake.mask.mask("lfinger01")
    fake.mask.mask("rfinger01")
    scene, _body = _scene_with_body()

    result = wf.place_hand_guides(scene, acurig=fake)

    assert result.ok is True
    assert result.masked_bones == ["lfinger01", "rfinger01"]


def test_t504_place_hand_guides_reuses_caller_provided_instance(monkeypatch):
    """Caller-supplied AcuRig must be used directly, not replaced."""
    _install_fake_accurig_with_mask(monkeypatch)
    caller = _FakeAcuRig()
    caller.mask = _FakeBoneMask()                            # type: ignore[attr-defined]
    scene, _body = _scene_with_body()

    result = wf.place_hand_guides(scene, acurig=caller)

    assert result.acurig is caller
    assert len(caller.place_calls) == 1


# ── T504 ▸ apply_hand_masks ────────────────────────────────────────────────
def test_t504_apply_hand_masks_no_body_returns_structured_error(monkeypatch):
    fake = _install_fake_accurig_with_mask(monkeypatch)
    scene = _make_scene("K1")  # empty

    result = wf.apply_hand_masks(scene, acurig=fake, masked_bones=["lhand"])

    assert result.ok is False
    assert result.code == "no_body"
    # AcuRig.mask must not have been touched.
    assert fake.mask.masked_bones == []


def test_t504_apply_hand_masks_no_acurig_returns_structured_error(monkeypatch):
    _install_fake_accurig_with_mask(monkeypatch)
    scene, _body = _scene_with_body()

    result = wf.apply_hand_masks(scene, acurig=None, masked_bones=["lhand"])

    assert result.ok is False
    assert result.code == "no_acurig"
    assert "place hand guides" in result.message.lower()


def test_t504_apply_hand_masks_applies_requested_set(monkeypatch):
    """Bones in ``masked_bones`` end up masked on the AcuRig instance."""
    fake = _install_fake_accurig_with_mask(monkeypatch)
    scene, _body = _scene_with_body()

    result = wf.apply_hand_masks(
        scene, acurig=fake,
        masked_bones=["lfinger01", "rfinger01", "lhand"],
    )

    assert result.ok is True
    assert result.code == "masked"
    assert set(fake.mask.masked_bones) == {"lfinger01", "rfinger01", "lhand"}
    assert set(result.masked_bones) == {"lfinger01", "rfinger01", "lhand"}


def test_t504_apply_hand_masks_unmasks_bones_no_longer_requested(monkeypatch):
    """Toggling a checkbox off must call ``BoneMask.unmask``."""
    fake = _install_fake_accurig_with_mask(monkeypatch)
    # Pre-seed both fingers + lhand as masked.
    fake.mask.mask("lfinger01")
    fake.mask.mask("rfinger01")
    fake.mask.mask("lhand")
    scene, _body = _scene_with_body()

    # Now request only the two fingers — lhand should get unmasked.
    result = wf.apply_hand_masks(
        scene, acurig=fake,
        masked_bones=["lfinger01", "rfinger01"],
    )

    assert result.ok is True
    assert set(fake.mask.masked_bones) == {"lfinger01", "rfinger01"}
    assert "lhand" not in fake.mask.masked_bones


def test_t504_apply_hand_masks_ignores_non_hand_bones(monkeypatch):
    """Bones outside HAND_BONES must be silently dropped, not crash."""
    fake = _install_fake_accurig_with_mask(monkeypatch)
    scene, _body = _scene_with_body()

    result = wf.apply_hand_masks(
        scene, acurig=fake,
        masked_bones=["lhand", "tail_root", "head"],
    )

    assert result.ok is True
    # tail_root / head should not have been forwarded to mask.mask().
    assert set(fake.mask.masked_bones) == {"lhand"}


def test_t504_apply_hand_masks_preserves_non_hand_bones_already_masked(monkeypatch):
    """Pre-existing non-hand mask entries (e.g. tail) must survive a hand
    toggle — T504 only owns the six hand bones, not the whole mask."""
    fake = _install_fake_accurig_with_mask(monkeypatch)
    fake.mask.mask("tail_root")        # body-level mask, pre-existing
    fake.mask.mask("lfinger01")
    scene, _body = _scene_with_body()

    result = wf.apply_hand_masks(
        scene, acurig=fake,
        masked_bones=["lfinger01"],     # unchanged
    )

    assert result.ok is True
    # tail_root must still be masked.
    assert "tail_root" in fake.mask.masked_bones
    assert "lfinger01" in fake.mask.masked_bones


def test_t504_apply_hand_masks_empty_list_clears_only_hand_bones(monkeypatch):
    """Empty masked-bones list must unmask every hand bone but preserve
    any non-hand bones masked by other workflow steps."""
    fake = _install_fake_accurig_with_mask(monkeypatch)
    fake.mask.mask("lhand")
    fake.mask.mask("rfinger01")
    fake.mask.mask("tail_root")
    scene, _body = _scene_with_body()

    result = wf.apply_hand_masks(scene, acurig=fake, masked_bones=[])

    assert result.ok is True
    # All hand bones should now be unmasked …
    for bone in wf.HAND_BONES:
        assert bone not in fake.mask.masked_bones
    # … but the body-level tail_root must remain.
    assert "tail_root" in fake.mask.masked_bones


# ── T505 ▸ available_preview_animations / play / stop ──────────────────────
class _FakeAnimation:
    """Stand-in for :class:`model_data.Animation` — just .name + .length."""

    def __init__(self, name: str, length: float = 1.0):
        self.name = name
        self.length = length


class _FakeViewport:
    """Stand-in for ``QtViewportWidget`` — records calls to
    :meth:`set_animation_pose` so tests can assert dispatch order."""

    def __init__(self):
        self.calls: list = []

    def set_animation_pose(self, pose, **kw):
        # Mirror the real signature (pose may be ``None`` for Stop).
        self.calls.append({"pose": pose, **kw})


def _body_with_anims(*names_and_lengths):
    """Return a (_FakeBodyModel, anim list) pair with the supplied
    animations attached so the workflow can enumerate them."""
    body = _FakeBodyModel("pfbcm")
    body.animations = [_FakeAnimation(n, ln) for n, ln in names_and_lengths]
    return body


def _scene_with_animated_body(*names_and_lengths):
    body = _body_with_anims(*names_and_lengths)
    scene = _make_scene("K1")
    scene.assign(md.PartSlot.HEADLESS_BODY, body,
                 resref="pfbcm", source_path="/tmp/pfbcm.mdl")
    return scene, body


def test_t505_preview_animations_constant_includes_idle_walk_talk():
    """PREVIEW_ANIMATIONS must cover the headline locomotion clips."""
    names = {n for _, n in wf.PREVIEW_ANIMATIONS}
    # walk + an idle (pause1) + a talk clip are mandatory.
    assert "walk" in names
    assert "pause1" in names
    # Either ``tlknorm`` or ``talk`` is accepted — pick whichever the
    # constant exports and assert at least one talk-like clip is present.
    assert any(n.startswith("tlk") or n == "talk" for n in names)


def test_t505_available_preview_animations_no_body_returns_structured_error():
    scene = _make_scene("K1")
    result = wf.available_preview_animations(scene)
    assert result.ok is False
    assert result.code == "no_body"


def test_t505_available_preview_animations_empty_animation_list():
    """A model with zero animations → ``no_animations`` code, missing
    list = full preview set."""
    scene, _body = _scene_with_animated_body()  # no anims
    result = wf.available_preview_animations(scene)
    assert result.ok is True
    assert result.code == "no_animations"
    assert result.available == []
    assert len(result.missing) == len(wf.PREVIEW_ANIMATIONS)


def test_t505_available_preview_animations_splits_available_vs_missing():
    """Mixed model: only walk+pause1 present → those are available, rest missing."""
    scene, _body = _scene_with_animated_body(
        ("walk", 1.0),
        ("pause1", 1.167),
        ("attack1", 1.0),                # not in preview set
    )
    result = wf.available_preview_animations(scene)
    assert result.ok is True
    assert result.code == "listed"
    avail_names = {n for _, n in result.available}
    miss_names  = {n for _, n in result.missing}
    assert "walk" in avail_names
    assert "pause1" in avail_names
    # attack1 is NOT in PREVIEW_ANIMATIONS so it shouldn't appear in either.
    assert "attack1" not in avail_names
    assert "attack1" not in miss_names
    # Anything else from PREVIEW_ANIMATIONS that's not present should be missing.
    for label, name in wf.PREVIEW_ANIMATIONS:
        if name not in avail_names:
            assert (label, name) in result.missing


def test_t505_available_preview_animations_case_insensitive_match():
    """Animation name matching must be case-insensitive."""
    scene, _body = _scene_with_animated_body(
        ("Walk", 1.0),                   # uppercase W
        ("PAUSE1", 1.167),               # uppercase
    )
    result = wf.available_preview_animations(scene)
    avail_names = {n for _, n in result.available}
    assert "walk" in avail_names
    assert "pause1" in avail_names


def test_t505_available_preview_animations_when_model_has_anims_but_none_preview():
    """Animations exist but none are in the preview set → no_animations + missing=all."""
    scene, _body = _scene_with_animated_body(
        ("attack1", 1.0),
        ("dead1", 1.0),
    )
    result = wf.available_preview_animations(scene)
    assert result.ok is True
    assert result.code == "no_animations"
    assert result.available == []
    # All entries from PREVIEW_ANIMATIONS should be in missing.
    miss_names = {n for _, n in result.missing}
    for _, name in wf.PREVIEW_ANIMATIONS:
        assert name in miss_names


# ── T505 ▸ play_preview_animation ──────────────────────────────────────────
def test_t505_play_preview_animation_no_body_returns_structured_error():
    scene = _make_scene("K1")
    result = wf.play_preview_animation(scene, "walk")
    assert result.ok is False
    assert result.code == "no_body"


def test_t505_play_preview_animation_empty_name_returns_anim_missing():
    scene, _body = _scene_with_animated_body(("walk", 1.0))
    result = wf.play_preview_animation(scene, "")
    assert result.ok is False
    assert result.code == "anim_missing"


def test_t505_play_preview_animation_missing_anim_returns_anim_missing():
    scene, _body = _scene_with_animated_body(("walk", 1.0))
    result = wf.play_preview_animation(scene, "dance")  # not on model
    assert result.ok is False
    assert result.code == "anim_missing"
    assert "dance" in result.message


def test_t505_play_preview_animation_dispatches_to_viewport_with_correct_args():
    """Happy path: viewport.set_animation_pose called with the matched
    Animation + name + length."""
    scene, _body = _scene_with_animated_body(("walk", 1.234))
    viewport = _FakeViewport()

    result = wf.play_preview_animation(scene, "walk", viewport=viewport)

    assert result.ok is True
    assert result.code == "playing"
    assert result.playing == "walk"
    assert abs(result.length - 1.234) < 1e-6
    # Exactly one dispatch call with the right kwargs.
    assert len(viewport.calls) == 1
    call = viewport.calls[0]
    assert getattr(call["pose"], "name", "") == "walk"
    assert call["name"] == "walk"
    assert abs(call["length"] - 1.234) < 1e-6
    assert call["time"] == 0.0


def test_t505_play_preview_animation_works_without_viewport():
    """When no viewport is passed, the workflow still validates + returns
    structured success — useful for headless testing of menu wiring."""
    scene, _body = _scene_with_animated_body(("walk", 1.0))
    result = wf.play_preview_animation(scene, "walk", viewport=None)
    assert result.ok is True
    assert result.code == "playing"
    assert result.playing == "walk"


def test_t505_play_preview_animation_case_insensitive_lookup():
    """Animation lookup matches case-insensitively."""
    scene, _body = _scene_with_animated_body(("Walk", 1.0))
    result = wf.play_preview_animation(scene, "walk")
    assert result.ok is True
    assert result.playing == "Walk"  # original-case name preserved


# ── M12 / T1204 ▸ motion assignment ────────────────────────────────────────
def test_t1204_assign_inherited_supermodel_sets_body_and_preview_list():
    scene, body = _scene_with_animated_body()
    body.supermodel = "NULL"

    result = wf.assign_motion_source(
        scene,
        wf.MOTION_SOURCE_INHERITED,
        supermodel="S_Female03",
    )
    preview = wf.available_preview_animations(scene)

    assert result.ok is True
    assert result.code == "inherited"
    assert body.supermodel == "S_Female03"
    assert scene.motion_assignment["source"] == wf.MOTION_SOURCE_INHERITED
    assert preview.code == "inherited"
    assert preview.available == list(wf.PREVIEW_ANIMATIONS)
    assert preview.missing == []


def test_t1204_animation_library_lists_real_supermodel_chain(monkeypatch):
    scene, body = _scene_with_animated_body()
    body.supermodel = "S_Male02"
    body.anim_scale = 1.0
    wf.assign_motion_source(
        scene,
        wf.MOTION_SOURCE_INHERITED,
        supermodel="S_Male02",
    )

    super_model = _FakeBodyModel("S_Male02")
    super_model.supermodel = "NULL"
    super_model.anim_scale = 1.0
    super_model.animations = [
        _FakeAnimation("pause1", 1.0),
        _FakeAnimation("walk", 1.2),
        _FakeAnimation("run", 0.8),
    ]

    class _RM:
        def load_model(self, resref, game="K1"):
            return super_model if str(resref).lower() == "s_male02" else None

    from src.core.animation.animation_engine import SuperModelResolver

    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(_RM())
    try:
        preview = wf.available_preview_animations(scene)
        library = wf.available_animation_library(scene)
    finally:
        SuperModelResolver.clear_cache()
        SuperModelResolver.configure(None)

    assert preview.code == "inherited"
    assert {name for _label, name in preview.available} == {"pause1", "walk", "run"}
    assert "tlknorm" in {name for _label, name in preview.missing}
    assert {name for _label, name in library.available} >= {"pause1", "walk", "run"}
    assert library.details["effective_supermodel"] == "S_Male02"


def test_t1204_animation_library_standard_supermodel_clips_populate(monkeypatch):
    scene, body = _scene_with_animated_body()
    body.supermodel = "NULL"
    body.anim_scale = 1.0
    wf.assign_motion_source(
        scene,
        wf.MOTION_SOURCE_INHERITED,
        supermodel="S_Male02",
    )

    super_model = _FakeBodyModel("S_Male02")
    super_model.supermodel = "NULL"
    super_model.anim_scale = 1.0
    super_model.animations = [
        _FakeAnimation("pause1", 1.0),
        _FakeAnimation("walk", 1.2),
        _FakeAnimation("run", 0.8),
        _FakeAnimation("tlknorm", 2.0),
    ]

    class _RM:
        def load_model(self, resref, game="K1"):
            return super_model if str(resref).lower() == "s_male02" else None

    from src.core.animation.animation_engine import SuperModelResolver

    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(_RM())
    try:
        library = wf.available_animation_library(scene)
    finally:
        SuperModelResolver.clear_cache()
        SuperModelResolver.configure(None)

    names = {name for _label, name in library.available}
    assert library.code == "listed"
    assert {"pause1", "walk", "run", "tlknorm"}.issubset(names)
    assert library.diagnostics == []
    assert library.details["resolved_supermodel"] == "S_Male02"


def test_t1204_animation_library_empty_reports_resolver_reason(monkeypatch):
    scene, body = _scene_with_animated_body()
    body.supermodel = "NULL"
    wf.assign_motion_source(
        scene,
        wf.MOTION_SOURCE_INHERITED,
        supermodel="S_Male02",
    )

    from src.core.animation.animation_engine import SuperModelResolver

    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)
    try:
        library = wf.available_animation_library(scene)
    finally:
        SuperModelResolver.clear_cache()

    assert library.code == "no_animations"
    assert library.available == []
    assert "resolver_not_configured" in library.diagnostics
    assert library.details["effective_supermodel"] == "S_Male02"
    assert "Diagnostics:" in library.message


def test_t1204_play_inherited_preview_succeeds_without_local_clip():
    scene, body = _scene_with_animated_body()
    body.supermodel = "NULL"
    wf.assign_motion_source(
        scene,
        wf.MOTION_SOURCE_INHERITED,
        supermodel="S_Female03",
    )

    result = wf.play_preview_animation(scene, "walk")

    assert result.ok is True
    assert result.code == "inherited_preview"
    assert result.playing == "walk"
    assert "S_Female03" in result.message


def test_t1204_imported_motion_assignment_reflects_preview_subset():
    scene, _body = _scene_with_animated_body()

    result = wf.assign_motion_source(
        scene,
        wf.MOTION_SOURCE_IMPORTED,
        imported_clips=["walk", "tlknorm", "attack1"],
    )
    preview = wf.available_preview_animations(scene)

    assert result.ok is True
    assert result.code == "imported_clips"
    assert {name for _label, name in preview.available} == {"walk", "tlknorm"}
    assert "attack1" not in {name for _label, name in preview.available}
    assert "pause1" in {name for _label, name in preview.missing}


def test_t1204_generated_rom_assignment_adds_rom_preview_entry():
    scene, _body = _scene_with_animated_body()

    result = wf.assign_motion_source(scene, wf.MOTION_SOURCE_ROM)
    preview = wf.available_preview_animations(scene)
    play = wf.play_preview_animation(scene, "generated_rom")

    assert result.ok is True
    assert result.code == "generated_rom"
    assert preview.available == [("ROM Test", "generated_rom")]
    assert play.ok is True
    assert play.code == "generated_rom"


def test_t1204_generated_rom_library_uses_selected_supermodel(monkeypatch):
    scene, body = _scene_with_animated_body()
    body.supermodel = "NULL"

    super_model = _FakeBodyModel("S_Male02")
    super_model.supermodel = "NULL"
    super_model.anim_scale = 1.0
    super_model.animations = [
        _FakeAnimation("pause1", 1.0),
        _FakeAnimation("walk", 1.2),
        _FakeAnimation("run", 0.8),
    ]

    class _RM:
        def load_model(self, resref, game="K1"):
            return super_model if str(resref).lower() == "s_male02" else None

    from src.core.animation.animation_engine import SuperModelResolver

    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(_RM())
    try:
        result = wf.assign_motion_source(
            scene,
            wf.MOTION_SOURCE_ROM,
            supermodel="S_Male02",
        )
        preview = wf.available_preview_animations(scene)
        library = wf.available_animation_library(scene)
    finally:
        SuperModelResolver.clear_cache()
        SuperModelResolver.configure(None)

    assert result.ok is True
    assert result.code == "generated_rom"
    assert body.supermodel == "S_Male02"
    assert scene.motion_assignment["supermodel"] == "S_Male02"
    assert preview.available == [("ROM Test", "generated_rom")]
    assert {name for _label, name in library.available} >= {"pause1", "walk", "run"}


def test_t903_run_rom_test_assigns_generated_rom_and_dispatches_viewport():
    scene, _body = _scene_with_animated_body()

    class _Viewport:
        calls = []

        def set_animation_pose(self, pose, **kwargs):
            self.calls.append((pose, kwargs))

    viewport = _Viewport()

    result = wf.run_rom_test(scene, viewport=viewport)
    preview = wf.available_preview_animations(scene)

    assert result.ok is True
    assert result.code == "generated_rom"
    assert result.playing == "generated_rom"
    assert result.length == 4.0
    assert scene.motion_assignment["source"] == wf.MOTION_SOURCE_ROM
    assert preview.available == [("ROM Test", "generated_rom")]
    assert viewport.calls == [
        (None, {"name": "generated_rom", "time": 0.0, "length": 4.0})
    ]


def test_t1204_export_validation_blocks_body_with_no_motion_source(monkeypatch):
    _make_check_service(monkeypatch, issues=[])
    scene, body = _scene_with_animated_body()
    body.supermodel = "NULL"

    result = wf.validate_for_export(scene)

    assert result.ok is False
    assert result.code == "blocked"
    assert "MOTIONS_MISSING" in result.blocking_codes


# ── T505 ▸ stop_preview_animation ──────────────────────────────────────────
def test_t505_stop_preview_animation_dispatches_none_to_viewport():
    viewport = _FakeViewport()
    result = wf.stop_preview_animation(viewport=viewport)
    assert result.ok is True
    assert result.code == "stopped"
    assert len(viewport.calls) == 1
    assert viewport.calls[0]["pose"] is None


def test_t505_stop_preview_animation_works_without_viewport():
    """No-op when no viewport is supplied — still returns ``stopped``."""
    result = wf.stop_preview_animation(viewport=None)
    assert result.ok is True
    assert result.code == "stopped"


# ── T506 ▸ validate_for_export / export_scene ──────────────────────────────
class _FakeSceneIO:
    """Stand-in for :class:`model_data.SceneIO` — records sidecar writes."""

    EXTENSION = ".ghostrig.json"
    written: list = []                    # class-level history for inspection

    @staticmethod
    def write_sidecar(scene, model_path):
        import os as _os
        base = _os.path.splitext(model_path)[0]
        sidecar = base + _FakeSceneIO.EXTENSION
        _FakeSceneIO.written.append({"scene": scene, "path": sidecar})
        # Don't actually write anything to disk — the tests only care
        # about the dispatch + returned path.
        return _os.path.abspath(sidecar)


def _install_fake_scene_io(monkeypatch):
    """Rebind ``wf._import_scene_io`` so export_scene uses _FakeSceneIO."""
    _FakeSceneIO.written = []             # reset history
    monkeypatch.setattr(wf, "_import_scene_io", lambda: _FakeSceneIO)
    return _FakeSceneIO


class _FakeMDLBinaryWriter:
    calls: list = []

    def write_files(self, model, mdl_path):
        from pathlib import Path
        _FakeMDLBinaryWriter.calls.append((model, mdl_path))
        p = Path(mdl_path)
        p.write_bytes(b"fake mdl")
        p.with_suffix(".mdx").write_bytes(b"fake mdx")


class _FakeFBXExporter:
    calls: list = []

    def export(self, model, path, *args, **kwargs):
        from pathlib import Path
        _FakeFBXExporter.calls.append((model, path, args, kwargs))
        Path(path).write_text("; fake fbx\n", encoding="utf-8")
        return True


class _FakeGLTFExporter:
    calls: list = []

    def export(self, model, path, *args, **kwargs):
        from pathlib import Path
        _FakeGLTFExporter.calls.append((model, path, args, kwargs))
        Path(path).write_bytes(b"fake glb")
        return True


class _FakeOBJExporter:
    calls: list = []

    def export(self, model, path, *args, **kwargs):
        from pathlib import Path
        _FakeOBJExporter.calls.append((model, path, args, kwargs))
        Path(path).write_text("# fake obj\n", encoding="utf-8")
        return True


def _install_fake_exporters(monkeypatch):
    """Rebind real writers so export_scene can be tested with fake models."""
    _FakeMDLBinaryWriter.calls = []
    _FakeFBXExporter.calls = []
    _FakeGLTFExporter.calls = []
    _FakeOBJExporter.calls = []
    monkeypatch.setattr(wf, "_import_mdl_binary_writer",
                        lambda: _FakeMDLBinaryWriter)
    monkeypatch.setattr(
        wf,
        "_import_mesh_exporters",
        lambda: (_FakeFBXExporter, _FakeGLTFExporter, _FakeOBJExporter),
    )
    monkeypatch.setattr(
        wf,
        "_load_exported_kotor_model",
        lambda _mdl_path: _FakeMDLBinaryWriter.calls[-1][0]
        if _FakeMDLBinaryWriter.calls else None,
    )
    return {
        "mdl": _FakeMDLBinaryWriter,
        "fbx": _FakeFBXExporter,
        "gltf": _FakeGLTFExporter,
        "obj": _FakeOBJExporter,
    }


# ── T506 ▸ validate_for_export ─────────────────────────────────────────────
def test_t506_validate_for_export_clean_scene_returns_clean(monkeypatch):
    _make_check_service(monkeypatch, issues=[])
    scene, _body = _scene_with_body("pfbcm")

    result = wf.validate_for_export(scene, strict=True)

    assert result.ok is True
    assert result.code == "clean"
    assert result.error_count == 0
    assert result.warning_count == 0
    assert result.info_count == 0
    assert result.blocking_codes == []


def test_t506_validate_for_export_warnings_only_is_not_blocked(monkeypatch):
    """Warnings + info must NOT block export per the T506 spec."""
    issues = [
        _FakeIssue("warning", "HOOK_MISSING", message="headhook missing"),
        _FakeIssue("info", "WEIGHT_ERRORS_TRUNCATED", message="…"),
    ]
    _make_check_service(monkeypatch, issues=issues)
    scene, _body = _scene_with_body("pfbcm")

    result = wf.validate_for_export(scene)

    assert result.ok is True
    assert result.code == "warnings_only"
    assert result.warning_count == 1
    assert result.info_count == 1
    assert result.blocking_codes == []


def test_t506_validate_for_export_errors_block_export(monkeypatch):
    """ERROR-severity issues MUST block export and surface their codes."""
    issues = [
        _FakeIssue("error", "BONE_MISSING", message="root bone missing"),
        _FakeIssue("error", "WEIGHT_OVERFLOW", message="vertex 42 > 4 bones"),
        _FakeIssue("warning", "HOOK_MISSING", message="headhook missing"),
    ]
    _make_check_service(monkeypatch, issues=issues)
    scene, _body = _scene_with_body("pfbcm")

    result = wf.validate_for_export(scene, strict=True)

    assert result.ok is False
    assert result.code == "blocked"
    assert result.error_count == 2
    assert result.warning_count == 1
    # Both error codes surface in blocking_codes (sorted, deduped).
    assert "BONE_MISSING" in result.blocking_codes
    assert "WEIGHT_OVERFLOW" in result.blocking_codes
    # Warnings are NOT in blocking_codes.
    assert "HOOK_MISSING" not in result.blocking_codes


def test_t506_validate_for_export_strict_passes_through_to_service(monkeypatch):
    """The ``strict`` kw must reach the ValidationService constructor."""
    captured: dict = {}

    class _RecordingService:
        def __init__(self, scene, *, strict: bool = False, **kw):
            captured["strict"] = strict

        def validate(self):
            return []

    class _Mod:
        ValidationService = _RecordingService

    monkeypatch.setattr(wf, "_import_validation_service", lambda: _Mod)
    scene, _body = _scene_with_body()

    wf.validate_for_export(scene, strict=True)
    assert captured["strict"] is True

    wf.validate_for_export(scene, strict=False)
    assert captured["strict"] is False


def test_t1005_head_export_requires_talk_animation(monkeypatch):
    _make_check_service(monkeypatch, issues=[])
    scene = _make_scene("K1")
    head = _FakeHeadModel("pfhc01")
    head.animations = []
    scene.assign(md.PartSlot.HEAD_SHELL, head, resref="pfhc01")
    scene.set_mode(md.CharacterMode.HEAD, locked=True)

    result = wf.validate_for_export(scene)

    assert result.ok is False
    assert "TALK_ANIMATION_MISSING" in result.blocking_codes


def test_t1005_head_export_allows_talk_animation(monkeypatch):
    _make_check_service(monkeypatch, issues=[])
    scene = _make_scene("K1")
    head = _FakeHeadModel("pfhc01")

    class _Anim:
        name = "talk"

    head.animations = [_Anim()]
    scene.assign(md.PartSlot.HEAD_SHELL, head, resref="pfhc01")
    scene.set_mode(md.CharacterMode.HEAD, locked=True)

    result = wf.validate_for_export(scene)

    assert result.ok is True
    assert "TALK_ANIMATION_MISSING" not in result.blocking_codes


def test_t1005_supermodel_export_requires_completed_snap(monkeypatch):
    _make_check_service(monkeypatch, issues=[])
    scene, _body = _scene_with_body("pfbcm")
    scene.assign(md.PartSlot.HEAD_SHELL, _FakeHeadModel("pfhc01"), resref="pfhc01")
    scene.set_mode(md.CharacterMode.SUPERMODEL, locked=True)

    result = wf.validate_for_export(scene)

    assert result.ok is False
    assert "COMPOSITE_SNAP_MISSING" in result.blocking_codes


def test_t1005_supermodel_export_allows_completed_snap(monkeypatch):
    _make_check_service(monkeypatch, issues=[])
    scene, _body = _scene_with_body("pfbcm")
    scene.assign(md.PartSlot.HEAD_SHELL, _FakeHeadModel("pfhc01"), resref="pfhc01")
    scene.set_mode(md.CharacterMode.SUPERMODEL, locked=True)
    scene.metadata["composite_snap"] = {
        "ok": True,
        "code": "snapped",
        "head_local_offset": [[1, 0, 0, 0],
                              [0, 1, 0, 0],
                              [0, 0, 1, 0],
                              [0, 0, 0, 1]],
    }

    result = wf.validate_for_export(scene)

    assert result.ok is True
    assert "COMPOSITE_SNAP_MISSING" not in result.blocking_codes


def test_t1005_creature_export_requires_generated_rom(monkeypatch):
    _make_check_service(monkeypatch, issues=[])
    scene, _body = _scene_with_body("c_bantha")
    scene.set_mode(md.CharacterMode.CREATURE, locked=True)

    result = wf.validate_for_export(scene)

    assert result.ok is False
    assert "ROM_CLIP_MISSING" in result.blocking_codes


def test_t1005_creature_export_allows_generated_rom(monkeypatch):
    _make_check_service(monkeypatch, issues=[])
    scene, _body = _scene_with_body("c_bantha")
    scene.set_mode(md.CharacterMode.CREATURE, locked=True)
    wf.assign_motion_source(scene, wf.MOTION_SOURCE_ROM)

    result = wf.validate_for_export(scene)

    assert result.ok is True
    assert "ROM_CLIP_MISSING" not in result.blocking_codes


# ── T506 ▸ export_scene ────────────────────────────────────────────────────
def test_t506_export_scene_no_body_returns_structured_error(monkeypatch):
    _install_fake_scene_io(monkeypatch)
    scene = _make_scene("K1")

    result = wf.export_scene(scene, formats=["kotor"], out_dir="/tmp/out")

    assert result.ok is False
    assert result.code == "no_body"
    assert result.formats == []
    assert _FakeSceneIO.written == []


def test_t506_export_scene_no_out_dir_returns_structured_error(monkeypatch):
    _install_fake_scene_io(monkeypatch)
    _make_check_service(monkeypatch, issues=[])
    scene, _body = _scene_with_body()

    result = wf.export_scene(scene, formats=["kotor"], out_dir="")

    assert result.ok is False
    assert result.code == "no_out_dir"


def test_t506_export_scene_no_formats_and_no_sidecar_returns_no_formats(
    monkeypatch, tmp_path,
):
    _install_fake_scene_io(monkeypatch)
    _make_check_service(monkeypatch, issues=[])
    scene, _body = _scene_with_body()

    result = wf.export_scene(
        scene, formats=[], out_dir=str(tmp_path), write_sidecar=False,
    )

    assert result.ok is False
    assert result.code == "no_formats"


def test_t506_export_scene_blocks_when_validation_has_errors(
    monkeypatch, tmp_path,
):
    """A pre-flight ERROR must short-circuit the export."""
    _install_fake_scene_io(monkeypatch)
    _make_check_service(monkeypatch, issues=[
        _FakeIssue("error", "BONE_MISSING", message="root missing"),
    ])
    scene, _body = _scene_with_body()

    result = wf.export_scene(
        scene, formats=["kotor"], out_dir=str(tmp_path),
        write_sidecar=True,
    )

    assert result.ok is False
    assert result.code == "blocked"
    # Nothing should have been dispatched to SceneIO.
    assert _FakeSceneIO.written == []


def test_t506_export_scene_skip_validation_bypasses_gate(monkeypatch, tmp_path):
    """``skip_validation=True`` must bypass the strict gate."""
    _install_fake_scene_io(monkeypatch)
    writers = _install_fake_exporters(monkeypatch)
    _make_check_service(monkeypatch, issues=[
        _FakeIssue("error", "BONE_MISSING", message="root missing"),
    ])
    scene, _body = _scene_with_body()

    result = wf.export_scene(
        scene, formats=["kotor"], out_dir=str(tmp_path),
        write_sidecar=True, skip_validation=True,
    )

    assert result.ok is True
    assert result.code == "exported"
    assert writers["mdl"].calls
    assert (tmp_path / "pfbcm.mdl").exists()
    assert (tmp_path / "pfbcm.mdx").exists()
    # Sidecar must have been written even though validation would have blocked.
    assert len(_FakeSceneIO.written) == 1


def test_t506_export_scene_writes_sidecar_to_out_dir(monkeypatch, tmp_path):
    """Sidecar JSON path lives next to ``<resref>.mdl`` in the out_dir."""
    _install_fake_scene_io(monkeypatch)
    _make_check_service(monkeypatch, issues=[])
    scene, _body = _scene_with_body("pfbcm")

    result = wf.export_scene(
        scene, formats=[], out_dir=str(tmp_path),
        write_sidecar=True,
    )

    assert result.ok is True
    assert _FakeSceneIO.written
    written = _FakeSceneIO.written[0]
    assert "pfbcm" in written["path"]
    assert written["path"].endswith(".ghostrig.json")
    # Resolved out_dir matches the request.
    assert result.out_dir == str(tmp_path)
    assert result.sidecar_path.endswith(".ghostrig.json")


def test_t506_export_scene_creates_missing_out_dir(monkeypatch, tmp_path):
    """The workflow must create the output directory when it doesn't exist."""
    _install_fake_scene_io(monkeypatch)
    _make_check_service(monkeypatch, issues=[])
    scene, _body = _scene_with_body()
    nested = tmp_path / "new" / "subdir"

    result = wf.export_scene(
        scene, formats=[], out_dir=str(nested), write_sidecar=True,
    )

    assert result.ok is True
    import os
    assert os.path.isdir(str(nested))


def test_t506_export_scene_per_format_rows_returned_in_request_order(
    monkeypatch, tmp_path,
):
    """Per-format rows preserve the order the caller asked for."""
    _install_fake_scene_io(monkeypatch)
    writers = _install_fake_exporters(monkeypatch)
    _make_check_service(monkeypatch, issues=[])
    scene, _body = _scene_with_body()

    result = wf.export_scene(
        scene, formats=["fbx", "kotor", "gltf", "obj"], out_dir=str(tmp_path),
        write_sidecar=False,
    )

    keys = [row.key for row in result.formats]
    assert keys == ["fbx", "kotor", "gltf", "obj"]
    assert result.ok is True
    for row in result.formats:
        assert row.code == "exported"
        assert row.ok is True
        # Each row's proposed path lives in out_dir.
        assert str(tmp_path) in row.path
    assert writers["fbx"].calls
    assert writers["mdl"].calls
    assert writers["gltf"].calls
    assert writers["obj"].calls
    assert (tmp_path / "pfbcm.fbx").exists()
    assert (tmp_path / "pfbcm.mdl").exists()
    assert (tmp_path / "pfbcm.mdx").exists()
    assert (tmp_path / "pfbcm.glb").exists()
    assert (tmp_path / "pfbcm.obj").exists()


def test_t1002_export_scene_records_sidecar_v2_format_results(
    monkeypatch, tmp_path,
):
    _install_fake_scene_io(monkeypatch)
    _install_fake_exporters(monkeypatch)
    _make_check_service(monkeypatch, issues=[])
    scene, _body = _scene_with_body()

    result = wf.export_scene(
        scene,
        formats=["kotor", "fbx"],
        out_dir=str(tmp_path),
        write_sidecar=True,
    )

    assert result.ok is True
    rows = scene.metadata["export_results"]
    assert [row["format"] for row in rows] == ["kotor", "fbx"]
    assert all(row["code"] == "exported" for row in rows)
    assert scene.metadata["validation_report"]["code"] == "clean"
    assert "last_export_at" in scene.metadata["export_timestamps"]


def test_t1004_default_export_formats_are_mode_aware():
    class _Mode:
        def __init__(self, value):
            self.value = value

    scene = _make_scene("K1")

    scene.mode = _Mode("headless_body")
    assert wf.default_export_formats_for_mode(scene) == ("kotor", "fbx", "gltf", "obj")

    scene.mode = _Mode("head")
    assert wf.default_export_formats_for_mode(scene) == ("kotor", "fbx", "gltf")

    scene.mode = _Mode("supermodel")
    assert wf.default_export_formats_for_mode(scene) == ("fbx", "gltf")

    scene.mode = _Mode("creature")
    assert wf.default_export_formats_for_mode(scene) == ("kotor", "fbx", "gltf", "obj")


def test_t506_export_scene_unknown_format_is_marked_failed(monkeypatch, tmp_path):
    """Unknown format keys are NOT silently dropped — they get a row
    with the ``failed`` code so the UI can flag them."""
    _install_fake_scene_io(monkeypatch)
    _install_fake_exporters(monkeypatch)
    _make_check_service(monkeypatch, issues=[])
    scene, _body = _scene_with_body()

    result = wf.export_scene(
        scene, formats=["kotor", "blender"], out_dir=str(tmp_path),
        write_sidecar=False,
    )

    keys = [row.key for row in result.formats]
    assert "blender" in keys
    assert next(r for r in result.formats if r.key == "kotor").ok is True
    blender = next(r for r in result.formats if r.key == "blender")
    assert blender.ok is False
    assert blender.code == "failed"


def test_t506_export_scene_writer_failure_returns_failed_row(monkeypatch, tmp_path):
    """A writer exception should not crash the workflow service."""
    _install_fake_scene_io(monkeypatch)
    _make_check_service(monkeypatch, issues=[])

    class _BrokenFBXExporter:
        def export(self, model, path, *args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(
        wf,
        "_import_mesh_exporters",
        lambda: (_BrokenFBXExporter, _FakeGLTFExporter, _FakeOBJExporter),
    )
    scene, _body = _scene_with_body()

    result = wf.export_scene(
        scene, formats=["fbx"], out_dir=str(tmp_path), write_sidecar=False,
    )

    assert result.ok is False
    assert result.code == "all_failed"
    assert result.formats[0].ok is False
    assert result.formats[0].code == "failed"
    assert "boom" in result.formats[0].message


def test_t506_export_scene_sanitises_resref_for_filenames(monkeypatch, tmp_path):
    """A resref containing path separators / spaces must be sanitised."""
    _install_fake_scene_io(monkeypatch)
    _install_fake_exporters(monkeypatch)
    _make_check_service(monkeypatch, issues=[])
    scene = _make_scene("K1")
    body = _FakeBodyModel("../weird name!")
    scene.assign(md.PartSlot.HEADLESS_BODY, body,
                 resref="../weird name!", source_path="/tmp/x.mdl")

    result = wf.export_scene(
        scene, formats=["kotor"], out_dir=str(tmp_path),
        write_sidecar=True,
    )

    assert result.ok is True
    # Output paths must NOT contain forbidden chars / parent refs.
    for row in result.formats:
        for ch in ("/", "\\", " ", "!", ".."):
            # Allow the os.sep itself in the out_dir prefix, but the
            # final basename must be sanitised.
            import os as _os
            base = _os.path.basename(row.path)
            assert ch not in base or ch == ".", \
                f"forbidden char {ch!r} in basename {base!r}"


def test_t506_export_formats_constant_exposes_all_four_targets():
    """EXPORT_FORMATS must declare KOTOR + FBX + glTF + OBJ in that order."""
    keys = [k for k, _label, _exts in wf.EXPORT_FORMATS]
    assert keys == ["kotor", "fbx", "gltf", "obj"]
    # Each entry has at least one extension.
    for key, label, exts in wf.EXPORT_FORMATS:
        assert label, f"format {key!r} has no display label"
        assert exts and all(e.startswith(".") for e in exts), \
            f"format {key!r} extensions look wrong: {exts}"


def test_external_texture_resolution_includes_skinned_fbx_meshes(tmp_path):
    """Bendak-style FBX skins expose textures on skin nodes, not rigid meshes."""
    model = _FakeTexturedSkinModel()
    fbx = tmp_path / "Bendak.fbx"
    fbx.write_bytes(b"fbx")
    tex_dir = tmp_path / "Texture"
    tex_dir.mkdir()
    tex = tex_dir / "BendakStarkiller_basecolor.png"
    tex.write_bytes(b"stub")

    dirs = wf.candidate_texture_dirs(str(fbx))
    report = wf.texture_resolution_report(model, dirs)

    assert str(tex_dir) in dirs
    assert wf.model_texture_names(model) == ["BendakStarkiller_basecolor"]
    assert report["found_count"] == 1
    assert report["missing"] == []
    assert report["found"]["BendakStarkiller_basecolor"] == str(tex)


def test_external_texture_export_writes_game_tga_for_skinned_mesh(tmp_path):
    Image = pytest.importorskip("PIL.Image")

    model = _FakeTexturedSkinModel()
    tex_dir = tmp_path / "Texture"
    tex_dir.mkdir()
    src = tex_dir / "BendakStarkiller_basecolor.png"
    Image.new("RGBA", (2, 2), (255, 0, 0, 255)).save(src)
    scene = _make_scene("K1")
    scene.metadata["external_texture_dirs"] = [str(tex_dir)]

    result = wf.export_external_textures(scene, model, str(tmp_path / "export"))

    assert result["ok"] is True
    assert result["missing"] == []
    assert len(result["written"]) == 1
    assert pathlib.Path(result["written"][0]).name == "BendakStarkiller_basecolor.tga"
    assert pathlib.Path(result["written"][0]).is_file()
    assert scene.metadata["external_texture_exports"] == result


def test_external_model_normalization_scales_to_kotor_humanoid_height():
    model = _FakeExternalMeshModel([
        (-1.0, -2.0, 0.0),
        (1.0, 2.0, 10.0),
    ])

    result = wf.normalize_external_model_for_kotor(
        model,
        game_version="K1",
        target_height=2.0,
    )

    assert result["ok"] is True
    assert result["vertical_axis"] == "z"
    assert abs(result["scale"] - 0.2) < 1e-6
    assert model.bb_min == pytest.approx((-0.2, -0.4, 0.0))
    assert model.bb_max == pytest.approx((0.2, 0.4, 2.0))
    assert model.metadata["kotor_normalization"]["target_height"] == 2.0


def test_external_model_normalization_maps_y_up_to_kotor_z():
    model = _FakeExternalMeshModel([
        (-1.0, 0.0, -0.25),
        (1.0, 10.0, 0.25),
    ])

    result = wf.normalize_external_model_for_kotor(
        model,
        game_version="K1",
        target_height=2.0,
    )

    assert result["ok"] is True
    assert result["vertical_axis"] == "y"
    assert model.bb_min[2] == pytest.approx(0.0)
    assert model.bb_max[2] == pytest.approx(2.0)


def test_external_model_normalization_fits_selected_reference_height():
    model = _FakeExternalMeshModel([
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 10.0),
    ])
    reference = _FakeExternalMeshModel([
        (-0.5, -0.5, 0.0),
        (0.5, 0.5, 1.75),
    ])

    result = wf.normalize_external_model_for_kotor(
        model,
        game_version="K1",
        reference_model=reference,
        reference_label="pmbam",
    )

    assert result["ok"] is True
    assert result["reference"] == "pmbam"
    assert result["target_height"] == pytest.approx(1.75)
    assert model.bb_max[2] == pytest.approx(1.75)


def test_external_model_normalization_snaps_to_selected_reference_frame():
    model = _FakeExternalMeshModel([
        (-1.0, -2.0, 0.0),
        (1.0, 2.0, 10.0),
    ])
    reference = _FakeExternalMeshModel([
        (4.5, -2.25, 0.25),
        (5.5, -1.75, 2.25),
    ])

    result = wf.normalize_external_model_for_kotor(
        model,
        game_version="K1",
        reference_model=reference,
        reference_label="n_mandalorian",
    )

    assert result["ok"] is True
    assert result["fit_policy"] == "selected_reference_bounds"
    assert result["target_center_xy"] == pytest.approx((5.0, -2.0))
    assert result["target_ground_z"] == pytest.approx(0.25)
    assert model.bb_min[2] == pytest.approx(0.25)
    assert model.bb_max[2] == pytest.approx(2.25)
    assert (model.bb_min[0] + model.bb_max[0]) * 0.5 == pytest.approx(5.0)
    assert (model.bb_min[1] + model.bb_max[1]) * 0.5 == pytest.approx(-2.0)


def test_external_model_normalization_uses_bone_landmarks_for_front_axis():
    model = _FakeExternalMeshModel([
        (-1.0, 0.0, -1.0),
        (1.0, 10.0, 1.0),
    ])
    for name, pos in [
        ("Hips", (0.0, 0.0, 0.0)),
        ("Head", (0.0, 10.0, 0.0)),
        ("LeftShoulder", (-1.0, 8.0, 0.0)),
        ("RightShoulder", (1.0, 8.0, 0.0)),
        ("LeftFoot", (-0.4, 0.0, -0.1)),
        ("RightFoot", (0.4, 0.0, -0.1)),
    ]:
        node = _FakeNode(name)
        node.position = pos
        model._nodes.append(node)

    reference = _FakeExternalMeshModel([
        (4.5, -2.25, 0.0),
        (5.5, -1.75, 2.0),
    ])
    for name, pos in [
        ("pelvis_g", (5.0, -2.0, 0.9)),
        ("headhook", (5.0, -2.0, 2.0)),
        ("lcollar_dum", (4.5, -2.0, 1.55)),
        ("rcollar_dum", (5.5, -2.0, 1.55)),
        ("lfoot_g", (4.8, -2.0, 0.0)),
        ("rfoot_g", (5.2, -2.0, 0.0)),
    ]:
        node = _FakeNode(name)
        node.position = pos
        reference._nodes.append(node)

    result = wf.normalize_external_model_for_kotor(
        model,
        game_version="K1",
        reference_model=reference,
        reference_label="n_mandalorian",
    )

    assert result["ok"] is True
    assert result["fit_policy"] == "bone_landmark_basis"
    assert result["scale_basis"] == "reference_bounds_height"
    assert result["vertical_axis"] == "bone_landmarks"
    assert result["source_fit_landmarks"]["side_pair"] == "shoulder"
    assert result["target_fit_landmarks"]["side_pair"] == "shoulder"
    assert result["scale"] == pytest.approx(0.2)
    assert model.bb_min[2] == pytest.approx(0.0)
    assert model.bb_max[2] == pytest.approx(2.0)
    assert (model.bb_min[0] + model.bb_max[0]) * 0.5 == pytest.approx(5.0)
    assert model.bb_max[1] > -2.0
    assert model.bb_min[1] < -2.0
    assert getattr(model._nodes[0], "_gr_vertices_in_kotor_world", False) is True


def test_external_model_normalization_fits_imported_joint_display_positions():
    model = _FakeExternalMeshModel([
        (-1.0, -1.0, 0.0),
        (1.0, 1.0, 10.0),
    ])
    joint = model._nodes[0]
    joint.position = (0.0, 0.0, 5.0)
    reference = _FakeExternalMeshModel([
        (9.5, 1.5, 0.25),
        (10.5, 2.5, 2.25),
    ])

    result = wf.normalize_external_model_for_kotor(
        model,
        game_version="K1",
        reference_model=reference,
        reference_label="n_mandalorian",
    )

    assert result["ok"] is True
    assert result["external_world_positions_fit"] is True
    assert joint.position == pytest.approx((0.0, 0.0, 1.0))
    assert joint.external_world_position == pytest.approx((10.0, 2.0, 1.25))


def test_manual_fit_adjustment_scales_about_ground_center():
    model = _FakeExternalMeshModel([
        (-1.0, -1.0, 0.0),
        (1.0, 1.0, 2.0),
    ])

    result = wf.apply_external_model_fit_adjustment(
        model,
        scale_delta=0.5,
    )

    assert result["ok"] is True
    assert model.bb_min == pytest.approx((-0.5, -0.5, 0.0))
    assert model.bb_max == pytest.approx((0.5, 0.5, 1.0))
    assert model.metadata["manual_fit_adjustment"]["scale"] == pytest.approx(0.5)


def test_manual_fit_adjustment_rotates_vertices_after_auto_fit():
    model = _FakeExternalMeshModel([
        (-1.0, -1.0, 0.0),
        (1.0, 1.0, 0.0),
    ])

    result = wf.apply_external_model_fit_adjustment(
        model,
        rotation_delta_degrees=(0.0, 0.0, 90.0),
    )

    assert result["ok"] is True
    verts = model._nodes[0].vertices
    assert verts[0] == pytest.approx((1.0, -1.0, 0.0))
    assert verts[1] == pytest.approx((-1.0, 1.0, 0.0))
    assert model.metadata["manual_fit_adjustment"]["rotation_degrees"] == pytest.approx((0.0, 0.0, 90.0))


def test_manual_fit_adjustment_translates_vertices_after_auto_fit():
    model = _FakeExternalMeshModel([
        (-1.0, -1.0, 0.0),
        (1.0, 1.0, 2.0),
    ])

    result = wf.apply_external_model_fit_adjustment(
        model,
        translation_delta=(0.25, -0.5, 0.75),
    )

    assert result["ok"] is True
    assert model.bb_min == pytest.approx((-0.75, -1.5, 0.75))
    assert model.bb_max == pytest.approx((1.25, 0.5, 2.75))
    assert model.metadata["manual_fit_adjustment"]["translation"] == pytest.approx((0.25, -0.5, 0.75))


def test_external_world_position_drives_bone_world_position():
    node = md.ModelNode(name="Head")
    node.position = (99.0, 99.0, 99.0)
    node.external_world_position = (1.0, 2.0, 3.0)

    assert node.bone_world_position() == (1.0, 2.0, 3.0)


def _fit_node(
    name: str,
    *,
    position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    parent=None,
    flags: int = int(md.NodeFlags.HEADER),
):
    node = md.ModelNode(name=name, flags=flags)
    node.position = position
    if parent is not None:
        node.parent = parent
        parent.children.append(node)
    return node


def _fit_humanoid_model(
    name: str,
    *,
    height: float,
    shoulder_width: float,
    foot_width: float,
    mesh_height: float | None = None,
):
    root = _fit_node(name)
    _fit_node("pelvis_g", position=(0.0, 0.0, height * 0.52), parent=root)
    _fit_node("head_g", position=(0.0, 0.0, height), parent=root)
    _fit_node("lcollar_g", position=(-shoulder_width * 0.5, 0.0, height * 0.78), parent=root)
    _fit_node("rcollar_g", position=(shoulder_width * 0.5, 0.0, height * 0.78), parent=root)
    _fit_node("lfoot_g", position=(-foot_width * 0.5, 0.0, 0.0), parent=root)
    _fit_node("rfoot_g", position=(foot_width * 0.5, 0.0, 0.0), parent=root)
    mesh = _fit_node(
        f"{name}_mesh",
        flags=int(md.NodeFlags.HEADER | md.NodeFlags.MESH),
        parent=root,
    )
    h = float(mesh_height if mesh_height is not None else height)
    mesh.vertices = [
        (-shoulder_width * 0.5, -0.05, 0.0),
        (shoulder_width * 0.5, 0.05, 0.0),
        (0.0, 0.0, h),
    ]
    mesh.faces = [(0, 1, 2)]
    return md.KotorModel(name=name, root_node=root)


def test_external_fit_report_uses_humanoid_landmarks_when_available():
    source = _fit_humanoid_model(
        "external_body",
        height=2.0,
        shoulder_width=1.0,
        foot_width=0.5,
    )
    reference = _fit_humanoid_model(
        "pmbam",
        height=1.6,
        shoulder_width=0.8,
        foot_width=0.4,
    )

    report = wf.inspect_external_model_fit(
        source,
        game_version="K1",
        reference_model=reference,
        reference_label="pmbam",
    )

    assert report["ok"] is True
    assert report["fit_policy"] == "bone_landmark_basis"
    assert report["scale_basis"] in {"reference_bounds_height", "bone_landmark_height"}
    assert report["reference"] == "pmbam"
    assert report["source_frame"]["landmarks"]["head"] == "head_g"
    assert report["target_frame"]["landmarks"]["head"] == "head_g"
    assert report["source_forward_axis"] == "+y"
    assert report["source_up_axis"] == "+z"
    assert report["target_forward_axis"] == "+y"
    assert report["target_up_axis"] == "+z"
    assert report["scale_factor"] == pytest.approx(0.8)
    assert report["height_source"] == "landmarks"
    assert report["ground_origin_basis"] == "feet"
    assert report["fallback_used"] is False
    assert report["confidence"] == pytest.approx(0.95)
    assert "source:head=head_g" in report["used_landmarks"]
    assert report["auto_fit_report"]["scale_factor"] == pytest.approx(0.8)
    assert report["auto_fit_report"]["used_landmarks"] == report["used_landmarks"]
    assert report["kotor_contract"]["native_skeleton_is_authority"] is True
    assert report["kotor_contract"]["imported_mesh_role"] == "payload_guest"


def test_normalization_persists_fit_report_in_model_metadata():
    source = _fit_humanoid_model(
        "external_body",
        height=2.0,
        shoulder_width=1.0,
        foot_width=0.5,
    )
    reference = _fit_humanoid_model(
        "pmbam",
        height=1.6,
        shoulder_width=0.8,
        foot_width=0.4,
    )

    result = wf.normalize_external_model_for_kotor(
        source,
        game_version="K1",
        reference_model=reference,
        reference_label="pmbam",
    )

    assert result["ok"] is True
    assert result["fit_policy"] == "bone_landmark_basis"
    assert "fit_report" in result
    assert source.metadata["kotor_fit_report"]["fit_policy"] == "bone_landmark_basis"
    assert (
        source.metadata["kotor_fit_report"]["auto_fit_report"]["source_forward_axis"]
        == "+y"
    )
    assert (
        source.metadata["kotor_fit_report"]["auto_fit_report"]["scale_factor"]
        == pytest.approx(0.8)
    )
    assert source.metadata["kotor_normalization"]["fit_report"]["reference"] == "pmbam"
    assert (
        source.metadata["kotor_fit_report"]["kotor_contract"]["final_dag_source"]
        == "selected_kotor_base"
    )


def test_external_fit_report_falls_back_to_bounds_when_landmarks_missing():
    root = _fit_node("import_root")
    mesh = _fit_node(
        "body_mesh",
        flags=int(md.NodeFlags.HEADER | md.NodeFlags.MESH),
        parent=root,
    )
    mesh.vertices = [(0.0, 0.0, 0.0), (0.2, 0.0, 0.0), (0.0, 0.2, 3.0)]
    mesh.faces = [(0, 1, 2)]
    source = md.KotorModel(name="body", root_node=root)

    report = wf.inspect_external_model_fit(source, game_version="K1")

    assert report["ok"] is True
    assert report["fit_policy"] == "origin_height"
    assert report["vertical_axis"] == "z"
    assert report["auto_fit_report"]["fallback_used"] is True
    assert report["auto_fit_report"]["height_source"] == "bounds"
    assert report["auto_fit_report"]["ground_origin_basis"] == "bounds_bottom"
    assert report["auto_fit_report"]["source_forward_axis"] == "unknown"
    assert report["auto_fit_report"]["source_up_axis"] == "+z"
    assert any("falling back to bounds" in warning for warning in report["warnings"])
