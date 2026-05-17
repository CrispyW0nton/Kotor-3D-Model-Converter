"""Regression tests for binary-FBX import fallback through Blender."""

from __future__ import annotations

import pathlib
import sys
from types import SimpleNamespace

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.core import gltf_importer as gi  # noqa: E402


def test_fbx_importer_uses_blender_fallback_when_trimesh_rejects_fbx(
    tmp_path,
    monkeypatch,
):
    fake_model = object()
    fbx = tmp_path / "Bendak.fbx"
    fbx.write_bytes(b"Kaydara FBX Binary  \x00\x1a\x00")

    import trimesh

    def reject_fbx(*_args, **_kwargs):
        raise ValueError("file_type 'fbx' not supported")

    monkeypatch.setattr(trimesh, "load", reject_fbx)
    monkeypatch.setattr(
        gi.FBXFallbackImporter,
        "_load_via_blender",
        lambda self, path, **kwargs: fake_model,
    )

    model = gi.FBXFallbackImporter().import_file(str(fbx), model_name="Bendak")

    assert model is fake_model


def test_blender_fallback_converts_then_imports_glb(tmp_path, monkeypatch):
    fbx = tmp_path / "Bendak.fbx"
    fbx.write_bytes(b"fbx")
    blender = tmp_path / "blender.exe"
    blender.write_text("fake", encoding="utf-8")
    fake_model = SimpleNamespace(name="Bendak")
    converted: list[tuple[str, pathlib.Path, pathlib.Path]] = []
    imported: list[pathlib.Path] = []

    def fake_convert(blender_exe, fbx_path, glb_path):
        converted.append((blender_exe, fbx_path, glb_path))
        glb_path.write_bytes(b"glb")

    class _FakeGLTFImporter:
        def import_file(self, path, **_kwargs):
            imported.append(pathlib.Path(path))
            return fake_model

    monkeypatch.setattr(gi, "_candidate_blender_executables", lambda: [str(blender)])
    monkeypatch.setattr(gi, "_convert_fbx_to_glb_with_blender", fake_convert)
    monkeypatch.setattr(gi, "GLTFImporter", _FakeGLTFImporter)

    result = gi.FBXFallbackImporter()._load_via_blender(
        str(fbx),
        model_name="Bendak",
        game_version=gi.GameVersion.K1,
        supermodel="NULL",
        classification="character",
    )

    assert result is fake_model
    assert converted[0][0] == str(blender)
    assert converted[0][1] == fbx
    assert converted[0][2].suffix == ".glb"
    assert imported[0].suffix == ".glb"


def test_candidate_blender_executables_honors_env_path(tmp_path, monkeypatch):
    blender = tmp_path / "blender.exe"
    blender.write_text("fake", encoding="utf-8")
    monkeypatch.setenv("GHOSTRIGGER_BLENDER_PATH", str(blender))
    monkeypatch.setattr(gi.shutil, "which", lambda _name: None)

    candidates = gi._candidate_blender_executables()

    assert candidates[0] == str(blender)
