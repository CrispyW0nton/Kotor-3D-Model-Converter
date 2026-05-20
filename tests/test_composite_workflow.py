"""
tests/test_composite_workflow.py - M7 / T701-T702 service tests.

The composite workflow is intentionally tested with fakes.  Real MDL
pipeline parity is covered by the MCP-driven scan suite; these tests
lock the Qt-free service contract and keep PySide6/PyKotor out of the
unit-test import path.
"""

from __future__ import annotations

import importlib.util as _il_util
import pathlib
import sys
from dataclasses import dataclass
from typing import Any, Optional

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load_module_direct(name: str, path: pathlib.Path):
    spec = _il_util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:                  # pragma: no cover
        raise ImportError(f"cannot create import spec for {path}")
    module = _il_util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


try:
    md = _load_module_direct(
        "ghostrigger_md_for_composite_wf",
        _SRC_DIR / "core" / "model_data.py",
    )
    wb = _load_module_direct(
        "ghostrigger_workflow_base_for_composite_wf",
        _SRC_DIR / "core" / "_workflow_base.py",
    )
    vs = _load_module_direct(
        "ghostrigger_validation_for_composite_wf",
        _SRC_DIR / "core" / "validation_service.py",
    )
    wf = _load_module_direct(
        "ghostrigger_composite_workflow_under_test",
        _SRC_DIR / "core" / "composite_workflow.py",
    )
    wf._import_model_data = lambda: md                       # type: ignore[attr-defined]
    wf._import_workflow_base = lambda: wb                     # type: ignore[attr-defined]
    wf._import_validation_service = lambda: vs                # type: ignore[attr-defined]
except Exception as exc:                                     # pragma: no cover
    pytest.skip(f"composite_workflow / model_data unavailable: {exc}",
                allow_module_level=True)


class _FakeNode:
    def __init__(
        self,
        name: str,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        parent: Optional["_FakeNode"] = None,
    ):
        self.name = name
        self.position = position
        self.rotation = rotation
        self.parent = parent
        self.children = []
        if parent is not None:
            parent.children.append(self)

    def world_transform(self):
        return self.position, self.rotation


class _FakeModel:
    def __init__(
        self,
        name: str,
        nodes,
        bb_min=(-0.5, -0.5, -0.1),
        bb_max=(0.5, 0.5, 0.8),
    ):
        self.name = name
        self.supermodel = "S_Female02"
        self.model_type = int(md.ModelClassification.CHARACTER)
        self._nodes = list(nodes)
        self.root_node = self._nodes[0] if self._nodes else None
        self.bb_min = bb_min
        self.bb_max = bb_max

    def all_nodes(self):
        return list(self._nodes)

    def compute_bounds(self):
        return None


def _body(name="pfbcm", hook_pos=(0.0, 0.0, 1.72), hook_rot=(0.0, 0.0, 0.0, 1.0)):
    root = _FakeNode("rootdummy")
    hook = _FakeNode("headhook", hook_pos, hook_rot, root)
    rhand = _FakeNode("rhand", parent=root)
    return _FakeModel(name, [root, hook, rhand])


def _head(name="pfhc01", bb_min=(-0.5, -0.5, -0.1), bb_max=(0.5, 0.5, 0.8)):
    root = _FakeNode("rootdummy")
    head_g = _FakeNode("head_g", parent=root)
    jaw = _FakeNode("f_jaw_g", parent=head_g)
    upper = _FakeNode("f_um_g", parent=head_g)
    talk = _FakeNode("talkdummy", parent=head_g)
    return _FakeModel(name, [root, head_g, jaw, upper, talk],
                      bb_min=bb_min, bb_max=bb_max)


def _make_scene():
    return md.CharacterScene(game_version="K1")


@dataclass
class _Load:
    ok: bool = True
    model: Any = None
    message: str = ""
    code: str = "loaded"
    resref: str = ""


class _BodyWorkflow:
    def __init__(self, model=None, ok=True, code="loaded"):
        self.model = model or _body()
        self.ok = ok
        self.code = code
        self.calls = []

    def load_body(self, path, scene, **kwargs):
        self.calls.append((path, kwargs))
        if self.ok:
            scene.assign(md.PartSlot.HEADLESS_BODY, self.model,
                         resref="pfbcm", source_path=path)
        return _Load(ok=self.ok, model=self.model,
                     message="body ok" if self.ok else "body failed",
                     code=self.code, resref="pfbcm")


class _HeadWorkflow:
    def __init__(self, model=None, ok=True, code="loaded"):
        self.model = model or _head()
        self.ok = ok
        self.code = code
        self.calls = []

    def load_head(self, path, scene, **kwargs):
        self.calls.append((path, kwargs))
        if self.ok:
            scene.assign(md.PartSlot.HEAD_SHELL, self.model,
                         resref="pfhc01", source_path=path)
        return _Load(ok=self.ok, model=self.model,
                     message="head ok" if self.ok else "head failed",
                     code=self.code, resref="pfhc01")


class _CharacterBuilder:
    @staticmethod
    def find_headhook(body_model):
        for node in body_model.all_nodes():
            if node.name.lower() == "headhook":
                return node.world_transform()
        return None


class _CreatureAppearance:
    calls = []
    fail = False

    @staticmethod
    def snap_head_onto_body(body_model, head_model, **kwargs):
        _CreatureAppearance.calls.append((body_model, head_model, kwargs))
        if _CreatureAppearance.fail:
            return {"ok": False, "model": None, "message": "preview failed", "warnings": []}
        return {"ok": True, "model": _FakeModel("preview", []),
                "message": "preview ok", "warnings": ["preview warning"]}


class _FakeSceneIO:
    written = []

    @staticmethod
    def write_sidecar(scene, anchor_path):
        path = pathlib.Path(anchor_path).with_suffix(".ghostrig.json")
        path.write_text("{}", encoding="utf-8")
        _FakeSceneIO.written.append((scene, str(path)))
        return str(path)


class _FakeFBXExporter:
    calls = []

    def export(self, model, path, *args, **kwargs):
        _FakeFBXExporter.calls.append((model, path, args, kwargs))
        pathlib.Path(path).write_text("; fake fbx\n", encoding="utf-8")
        return True


class _FakeGLTFExporter:
    calls = []

    def export(self, model, path, *args, **kwargs):
        _FakeGLTFExporter.calls.append((model, path, args, kwargs))
        pathlib.Path(path).write_bytes(b"glTF")
        return True


class _FakeOBJExporter:
    calls = []

    def export(self, model, path, *args, **kwargs):
        _FakeOBJExporter.calls.append((model, path, args, kwargs))
        pathlib.Path(path).write_text("# fake obj\n", encoding="utf-8")
        return True


def _install_backends(monkeypatch, body_wf=None, head_wf=None):
    body_wf = body_wf or _BodyWorkflow()
    head_wf = head_wf or _HeadWorkflow()
    _CreatureAppearance.calls = []
    _CreatureAppearance.fail = False
    monkeypatch.setattr(wf, "_import_body_workflow", lambda: body_wf)
    monkeypatch.setattr(wf, "_import_head_workflow", lambda: head_wf)
    monkeypatch.setattr(wf, "_import_character_builder", lambda: _CharacterBuilder)
    monkeypatch.setattr(wf, "_import_creature_appearance", lambda: _CreatureAppearance)
    return body_wf, head_wf


def _install_export_backends(monkeypatch):
    _FakeSceneIO.written = []
    _FakeFBXExporter.calls = []
    _FakeGLTFExporter.calls = []
    _FakeOBJExporter.calls = []
    monkeypatch.setattr(wf, "_import_scene_io", lambda: _FakeSceneIO)
    monkeypatch.setattr(
        wf,
        "_import_mesh_exporters",
        lambda: (_FakeFBXExporter, _FakeGLTFExporter, _FakeOBJExporter),
    )


def test_t701_load_composite_loads_body_head_and_sets_supermodel_mode(monkeypatch):
    scene = _make_scene()
    body_wf, head_wf = _install_backends(monkeypatch)

    result = wf.load_composite(
        scene,
        body_path="C:/tmp/pfbcm.mdl",
        head_path="C:/tmp/pfhc01.mdl",
        game_version="K1",
    )

    assert result.ok is True
    assert result.code == "loaded"
    assert result.body_result.ok is True
    assert result.head_result.ok is True
    assert scene.mode == md.CharacterMode.SUPERMODEL
    assert scene.mode_locked is False
    assert scene.get_model(md.PartSlot.HEADLESS_BODY) is body_wf.model
    assert scene.get_model(md.PartSlot.HEAD_SHELL) is head_wf.model


def test_t701_load_composite_passes_game_version_to_child_workflows(monkeypatch):
    scene = _make_scene()
    body_wf, head_wf = _install_backends(monkeypatch)

    wf.load_composite(
        scene,
        body_path="body.mdl",
        head_path="head.mdl",
        game_version="K2",
        allow_mode_correction=True,
    )

    assert body_wf.calls[0][1]["game_version"] == "K2"
    assert body_wf.calls[0][1]["allow_mode_correction"] is True
    assert head_wf.calls[0][1]["game_version"] == "K2"
    assert head_wf.calls[0][1]["allow_mode_correction"] is True


def test_t701_load_composite_stops_when_body_fails(monkeypatch):
    scene = _make_scene()
    body_wf = _BodyWorkflow(ok=False, code="file_not_found")
    head_wf = _HeadWorkflow()
    _install_backends(monkeypatch, body_wf=body_wf, head_wf=head_wf)

    result = wf.load_composite(scene, body_path="missing.mdl", head_path="head.mdl")

    assert result.ok is False
    assert result.code == "file_not_found"
    assert result.head_result is None
    assert head_wf.calls == []


def test_t701_load_composite_stops_when_head_fails(monkeypatch):
    scene = _make_scene()
    head_wf = _HeadWorkflow(ok=False, code="mode_mismatch")
    _install_backends(monkeypatch, head_wf=head_wf)

    result = wf.load_composite(scene, body_path="body.mdl", head_path="bad.mdl")

    assert result.ok is False
    assert result.code == "mode_mismatch"
    assert result.body_result.ok is True
    assert result.head_result.ok is False


def test_t702_snap_head_to_body_requires_body(monkeypatch):
    scene = _make_scene()
    scene.assign(md.PartSlot.HEAD_SHELL, _head(), resref="pfhc01")
    _install_backends(monkeypatch)

    snap = wf.snap_head_to_body(scene)

    assert snap.ok is False
    assert snap.code == "no_body"
    assert scene.metadata["composite_snap"]["code"] == "no_body"


def test_t702_snap_head_to_body_requires_head(monkeypatch):
    scene = _make_scene()
    scene.assign(md.PartSlot.HEADLESS_BODY, _body(), resref="pfbcm")
    _install_backends(monkeypatch)

    snap = wf.snap_head_to_body(scene)

    assert snap.ok is False
    assert snap.code == "no_head"
    assert scene.metadata["composite_snap"]["code"] == "no_head"


def test_t702_snap_head_to_body_reports_missing_headhook(monkeypatch):
    scene = _make_scene()
    no_hook = _FakeModel("pfbcm", [_FakeNode("rootdummy"), _FakeNode("rhand")])
    scene.assign(md.PartSlot.HEADLESS_BODY, no_hook, resref="pfbcm")
    scene.assign(md.PartSlot.HEAD_SHELL, _head(), resref="pfhc01")
    _install_backends(monkeypatch)

    snap = wf.snap_head_to_body(scene)

    assert snap.ok is False
    assert snap.code == "headhook_missing"
    assert scene.metadata["composite_snap"]["headhook"] is None


def test_t702_snap_head_to_body_writes_matrix_and_head_metadata(monkeypatch):
    scene = _make_scene()
    body = _body(hook_pos=(1.0, 2.0, 3.0))
    head = _head()
    scene.assign(md.PartSlot.HEADLESS_BODY, body, resref="pfbcm")
    scene.assign(md.PartSlot.HEAD_SHELL, head, resref="pfhc01")
    _install_backends(monkeypatch)

    snap = wf.snap_head_to_body(scene)

    assert snap.ok is True
    assert snap.code == "snapped"
    assert snap.head_local_offset[0][3] == pytest.approx(1.0)
    assert snap.head_local_offset[1][3] == pytest.approx(2.0)
    assert snap.head_local_offset[2][3] == pytest.approx(3.0)
    assert head.composite_parent_hook == "headhook"
    assert head.head_local_offset == snap.head_local_offset
    assert scene.metadata["composite_snap"]["head_root"] == "rootdummy"


def test_t702_snap_head_to_body_delegates_preview_to_existing_backend(monkeypatch):
    scene = _make_scene()
    scene.assign(md.PartSlot.HEADLESS_BODY, _body(), resref="pfbcm")
    scene.assign(md.PartSlot.HEAD_SHELL, _head(), resref="pfhc01")
    _install_backends(monkeypatch)

    snap = wf.snap_head_to_body(scene, build_preview=True)

    assert snap.preview_model.name == "preview"
    assert snap.warnings == ["preview warning"]
    assert len(_CreatureAppearance.calls) == 1
    assert _CreatureAppearance.calls[0][2]["scale_head"] is False
    assert _CreatureAppearance.calls[0][2]["merge_animations"] is False


def test_t702_snap_head_to_body_can_skip_preview(monkeypatch):
    scene = _make_scene()
    scene.assign(md.PartSlot.HEADLESS_BODY, _body(), resref="pfbcm")
    scene.assign(md.PartSlot.HEAD_SHELL, _head(), resref="pfhc01")
    _install_backends(monkeypatch)

    snap = wf.snap_head_to_body(scene, build_preview=False)

    assert snap.ok is True
    assert snap.preview_model is None
    assert _CreatureAppearance.calls == []


def test_t702_update_snap_after_scene_mutation_recomputes_metadata(monkeypatch):
    scene = _make_scene()
    body = _body(hook_pos=(0.0, 0.0, 1.0))
    scene.assign(md.PartSlot.HEADLESS_BODY, body, resref="pfbcm")
    scene.assign(md.PartSlot.HEAD_SHELL, _head(), resref="pfhc01")
    _install_backends(monkeypatch)

    first = wf.update_snap_after_scene_mutation(scene, build_preview=False)
    hook = body.all_nodes()[1]
    hook.position = (0.0, 0.0, 2.0)
    second = wf.update_snap_after_scene_mutation(scene, build_preview=False)

    assert first.head_local_offset[2][3] == pytest.approx(1.0)
    assert second.head_local_offset[2][3] == pytest.approx(2.0)
    assert scene.metadata["composite_snap"]["head_local_offset"][2][3] == pytest.approx(2.0)


def test_t702_preview_failure_is_warning_not_snap_failure(monkeypatch):
    scene = _make_scene()
    scene.assign(md.PartSlot.HEADLESS_BODY, _body(), resref="pfbcm")
    scene.assign(md.PartSlot.HEAD_SHELL, _head(), resref="pfhc01")
    _install_backends(monkeypatch)
    _CreatureAppearance.fail = True

    snap = wf.snap_head_to_body(scene, build_preview=True)

    assert snap.ok is True
    assert snap.preview_model is None
    assert "preview failed" in snap.warnings


def test_t702_check_composite_reports_missing_parts(monkeypatch):
    scene = _make_scene()
    _install_backends(monkeypatch)

    result = wf.check_composite(scene)

    assert result.ok is False
    assert result.code == "blocked"
    assert {"COMPOSITE_BODY_MISSING", "COMPOSITE_HEAD_MISSING"} <= result.codes
    assert result.error_count == 2


def test_t702_check_composite_clean_pair(monkeypatch):
    scene = _make_scene()
    scene.assign(md.PartSlot.HEADLESS_BODY, _body(), resref="pfbcm")
    scene.assign(md.PartSlot.HEAD_SHELL, _head(), resref="pfhc01")
    _install_backends(monkeypatch)

    result = wf.check_composite(scene)

    assert result.ok is True
    assert result.code == "clean"
    assert result.summary == "CLEAN"


def test_t703_check_composite_flags_unknown_body_supermodel(monkeypatch):
    scene = _make_scene()
    body = _body()
    body.supermodel = "C_BANTHA"
    scene.assign(md.PartSlot.HEADLESS_BODY, body, resref="pfbcm")
    scene.assign(md.PartSlot.HEAD_SHELL, _head(), resref="pfhc01")
    _install_backends(monkeypatch)

    result = wf.check_composite(scene, strict=True)

    assert result.ok is False
    assert result.code == "blocked"
    assert "SUPERMODEL_MISMATCH" in result.codes
    assert result.error_count == 2


def test_t703_check_composite_flags_body_head_supermodel_mismatch(monkeypatch):
    scene = _make_scene()
    body = _body()
    head = _head()
    body.supermodel = "S_Female02"
    head.supermodel = "S_Male02"
    scene.assign(md.PartSlot.HEADLESS_BODY, body, resref="pfbcm")
    scene.assign(md.PartSlot.HEAD_SHELL, head, resref="pfhc01")
    _install_backends(monkeypatch)

    result = wf.check_composite(scene)

    assert result.ok is True
    assert result.code == "warnings_only"
    assert "SUPERMODEL_MISMATCH" in result.codes
    assert result.warning_count == 1


def test_t705_check_composite_warns_on_headhook_seam_gap(monkeypatch):
    scene = _make_scene()
    scene.assign(md.PartSlot.HEADLESS_BODY, _body(), resref="pfbcm")
    # A custom head whose entire local bbox starts 12 cm above its root would
    # leave the headhook below the visible head geometry after attachment.
    scene.assign(md.PartSlot.HEAD_SHELL, _head(bb_min=(-0.5, -0.5, 0.12)),
                 resref="custom_head")
    _install_backends(monkeypatch)

    result = wf.check_composite(scene)

    assert result.ok is True
    assert result.code == "warnings_only"
    assert "SEAM_GAP" in result.codes
    assert "12.0 cm" in result.issues[0].message


def test_t1003_export_composite_writes_fbx_gltf_and_sidecar(monkeypatch, tmp_path):
    scene = _make_scene()
    scene.assign(md.PartSlot.HEADLESS_BODY, _body(), resref="pfbcm")
    scene.assign(md.PartSlot.HEAD_SHELL, _head(), resref="pfhc01")
    scene.set_mode(md.CharacterMode.SUPERMODEL, locked=True)
    _install_backends(monkeypatch)
    _install_export_backends(monkeypatch)

    result = wf.export_composite_scene(
        scene,
        formats=["fbx", "gltf"],
        out_dir=str(tmp_path),
        write_sidecar=True,
        skip_validation=True,
    )

    assert result.ok is True
    assert result.code == "exported"
    assert [row.key for row in result.formats] == ["fbx", "gltf"]
    assert all(row.code == "exported" for row in result.formats)
    assert (tmp_path / "pfbcm_pfhc01_composite.fbx").exists()
    assert (tmp_path / "pfbcm_pfhc01_composite.glb").exists()
    assert result.sidecar_path.endswith(".ghostrig.json")
    assert _FakeFBXExporter.calls[0][0].name == "pfbcm_pfhc01_composite"
    assert _FakeGLTFExporter.calls[0][3]["binary"] is True
    assert scene.metadata["composite_export"]["resref"] == "pfbcm_pfhc01_composite"
    assert scene.metadata["composite_snap"]["code"] == "snapped"


def test_t1003_export_composite_rejects_non_interchange_format(monkeypatch, tmp_path):
    scene = _make_scene()
    scene.assign(md.PartSlot.HEADLESS_BODY, _body(), resref="pfbcm")
    scene.assign(md.PartSlot.HEAD_SHELL, _head(), resref="pfhc01")
    _install_backends(monkeypatch)
    _install_export_backends(monkeypatch)

    result = wf.export_composite_scene(
        scene,
        formats=["kotor"],
        out_dir=str(tmp_path),
        write_sidecar=False,
        skip_validation=True,
    )

    assert result.ok is False
    assert result.code == "all_failed"
    assert result.formats[0].code == "failed"
    assert "FBX/glTF only" in result.formats[0].message


def test_t1003_export_composite_blocks_without_headhook_snap(monkeypatch, tmp_path):
    scene = _make_scene()
    scene.assign(
        md.PartSlot.HEADLESS_BODY,
        _FakeModel("pfbcm", [_FakeNode("rootdummy"), _FakeNode("rhand")]),
        resref="pfbcm",
    )
    scene.assign(md.PartSlot.HEAD_SHELL, _head(), resref="pfhc01")
    _install_backends(monkeypatch)
    _install_export_backends(monkeypatch)

    result = wf.export_composite_scene(
        scene,
        formats=["fbx"],
        out_dir=str(tmp_path),
        write_sidecar=False,
        skip_validation=True,
    )

    assert result.ok is False
    assert result.code == "merge_failed"
    assert "headhook" in result.message.lower()


def test_t703_known_pc_supermodel_constant_is_uppercase():
    assert "S_FEMALE02" in wf.KOTOR_PC_SUPERMODELS
    assert all(value == value.upper() for value in wf.KOTOR_PC_SUPERMODELS)


def test_t701_character_builder_load_button_routes_supermodel_to_composite():
    source = (_SRC_DIR / "gui" / "panels" / "qt_character_builder_panel.py").read_text(
        encoding="utf-8"
    )
    assert 'self._is_scene_mode("supermodel")' in source
    assert "self._on_load_composite_requested()" in source
    assert "composite_workflow" in source
    assert "_cw.load_composite" in source
    assert "COMPOSITE_LOADED" in source


def test_t702_character_builder_check_button_routes_supermodel_to_composite():
    source = (_SRC_DIR / "gui" / "panels" / "qt_character_builder_panel.py").read_text(
        encoding="utf-8"
    )
    assert 'self._is_scene_mode("supermodel")' in source
    assert "check_composite" in source


def test_t1003_character_builder_export_routes_supermodel_to_composite():
    source = (_SRC_DIR / "gui" / "panels" / "qt_character_builder_panel.py").read_text(
        encoding="utf-8"
    )
    assert 'self._is_scene_mode("supermodel")' in source
    assert "export_composite_scene" in source


def test_launch_hud_defaults_to_accurig_like_body_workflow():
    source = (_SRC_DIR / "gui" / "panels" / "qt_character_builder_panel.py").read_text(
        encoding="utf-8"
    )
    assert "apply_theme(self)" in source
    assert "CharacterMode.HEADLESS_BODY" in source
    assert "CharacterBuilderToolbarBrand" in source
    assert "GHOSTRIGGER AUTORIG" in source


def test_workflow_rail_uses_accurig_step_language_and_button_styling():
    source = (_SRC_DIR / "gui" / "panels" / "qt_workflow_rail.py").read_text(
        encoding="utf-8"
    )
    assert "Choose Base + Load Mesh" in source
    assert "Assign Skeleton" in source
    assert "Assign Animations" in source
    assert "Preview" in source
    assert "Export MDL" in source
    assert "GuidedRigRailBrand" in source
    assert "border:1px solid {C.get('accent'" in source
