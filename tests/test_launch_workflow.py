"""M12/T1205 one-shot external mesh launch workflow proof."""

from __future__ import annotations

import importlib.util as _il_util
import os
import pathlib
import sys

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
        "ghostrigger_launch_md_under_test",
        _SRC_DIR / "core" / "geometry" / "model_data.py",
    )
    wf = _load_module_direct(
        "ghostrigger_launch_workflow_under_test",
        _SRC_DIR / "core" / "characters" / "headless_body_workflow.py",
    )
    wf._import_model_data = lambda: md                       # type: ignore[attr-defined]
except Exception as exc:                                    # pragma: no cover
    pytest.skip(f"workflow / model_data unavailable: {exc}",
                allow_module_level=True)


class _FakeNode:
    def __init__(
        self,
        name: str,
        *,
        is_mesh: bool = False,
        is_skin: bool = False,
        vertices=None,
        skin_data=None,
    ):
        self.name = name
        self.is_mesh = is_mesh
        self.is_skin = is_skin
        self.vertices = list(vertices or [])
        self.skin_data = skin_data
        self.children = []


class _FakeModel:
    def __init__(self, name: str, *, supermodel: str = "NULL", skinned: bool = False):
        self.name = name
        self.supermodel = supermodel
        self.model_type = int(md.ModelClassification.CHARACTER)
        self.animations = []
        self._nodes = [
            _FakeNode("rootdummy"),
            _FakeNode("headhook"),
            _FakeNode("rhand"),
            _FakeNode(
                "external_body",
                is_mesh=True,
                is_skin=skinned,
                vertices=[(0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)],
                skin_data={"weights": [1.0]} if skinned else None,
            ),
        ]
        self.root_node = self._nodes[0]

    def all_nodes(self):
        return list(self._nodes)


class _FakeValidationService:
    def __init__(self, scene, *, strict: bool = False, **_kw):
        self.scene = scene
        self.strict = strict

    def validate(self):
        return []


class _FakeValidationModule:
    ValidationService = _FakeValidationService


class _FakeSceneIO:
    @staticmethod
    def write_sidecar(scene, model_path):
        sidecar = os.path.splitext(model_path)[0] + ".ghostrig.json"
        pathlib.Path(sidecar).write_text("{}", encoding="utf-8")
        return sidecar


class _FakeWriter:
    def write_files(self, model, mdl_path):
        pathlib.Path(mdl_path).write_bytes(b"fake launch mdl")
        pathlib.Path(os.path.splitext(mdl_path)[0] + ".mdx").write_bytes(
            b"fake launch mdx"
        )


def _install_launch_fakes(monkeypatch, *, reloaded_model):
    external = _FakeModel("external_body", supermodel="NULL", skinned=False)
    rigged = _FakeModel("external_body", supermodel="S_Female03", skinned=True)
    template = _FakeModel("gr_body_k1", supermodel="S_Female03", skinned=True)

    monkeypatch.setattr(wf, "_load_gltf_or_mesh", lambda _path, _gv: external)

    class _FakeCharacterBuilder:
        @staticmethod
        def load_template(game="K1", part="body"):
            return template

        @staticmethod
        def apply_template_rig(mesh_model, template_model, game="K1"):
            assert mesh_model is external
            assert template_model is template
            return {
                "ok": True,
                "model": rigged,
                "message": "Template rig applied.",
                "warnings": [],
                "scale": 1.0,
            }

    monkeypatch.setattr(wf, "_import_character_builder", lambda: _FakeCharacterBuilder)
    monkeypatch.setattr(wf, "_import_validation_service", lambda: _FakeValidationModule)
    monkeypatch.setattr(wf, "_import_mdl_binary_writer", lambda: _FakeWriter)
    monkeypatch.setattr(wf, "_import_scene_io", lambda: _FakeSceneIO)
    monkeypatch.setattr(
        wf,
        "place_body_guides",
        lambda scene: wf.BodyRigGuidesResult(
            ok=True,
            guides={"pelvis": object(), "headhook": object()},
            acurig=object(),
            message="Placed guides.",
        ),
    )
    monkeypatch.setattr(
        wf,
        "generate_skeleton",
        lambda scene, **_kw: wf.BodyRigGenerateResult(
            ok=True,
            bone_count=2,
            vertices_skinned=3,
            message="Generated skeleton.",
            code="generated",
        ),
    )
    monkeypatch.setattr(wf, "_load_exported_kotor_model", lambda _path: reloaded_model)
    return external, rigged


def test_t1205_external_mesh_launch_workflow_exports_reloads_and_verifies(tmp_path, monkeypatch):
    """The launch path should prove the modder's core OBJ/FBX-to-MDL story."""
    _external, rigged = _install_launch_fakes(monkeypatch, reloaded_model=None)
    monkeypatch.setattr(wf, "_load_exported_kotor_model", lambda _path: rigged)

    mesh = tmp_path / "custom_body.obj"
    mesh.write_text("o custom_body\nv 0 0 0\nv 0 1 0\nv 1 0 0\nf 1 2 3\n",
                    encoding="utf-8")
    scene = md.CharacterScene(game_version="K1")

    result = wf.run_external_mesh_launch_workflow(
        str(mesh),
        scene=scene,
        game_version="K1",
        out_dir=str(tmp_path / "export"),
        motion_supermodel="S_Female03",
    )

    assert result.ok is True
    assert result.code == "launch_verified"
    assert pathlib.Path(result.mdl_path).is_file()
    assert pathlib.Path(result.mdx_path).is_file()
    assert pathlib.Path(result.export_result.sidecar_path).is_file()
    assert result.supermodel == "S_Female03"
    assert result.mesh_count >= 1
    assert result.skin_node_count >= 1
    assert {"headhook", "rhand"}.issubset({h.lower() for h in result.hooks})
    assert scene.motion_assignment["source"] == wf.MOTION_SOURCE_INHERITED


def test_t1205_launch_workflow_fails_when_reloaded_export_has_no_skin(tmp_path, monkeypatch):
    bad_reload = _FakeModel("external_body", supermodel="S_Female03", skinned=False)
    _install_launch_fakes(monkeypatch, reloaded_model=bad_reload)
    mesh = tmp_path / "custom_body.obj"
    mesh.write_text("o custom_body\nv 0 0 0\n", encoding="utf-8")

    result = wf.run_external_mesh_launch_workflow(
        str(mesh),
        scene=md.CharacterScene(game_version="K1"),
        game_version="K1",
        out_dir=str(tmp_path / "export"),
        motion_supermodel="S_Female03",
    )

    assert result.ok is False
    assert result.code == "verification_failed"
    assert "no skinned mesh" in result.message.lower()
