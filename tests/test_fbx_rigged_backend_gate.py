"""Rigged/animated FBX exports must bypass the Autodesk SDK backend.

2026-07-15 user report: baking animations onto the republic soldier female
and exporting FBX produced a scrambled model in 3ds Max/Unity.  Root cause:
when the ``fbx`` Python module is installed, ``FBXExporter.export`` preferred
the SDK backend, which writes skeleton nodes translation-only (no rotation),
builds no skin clusters, and exports no animation takes.  The zero-dependency
ASCII 7.4 writer supports all three, so skinned or animated models must
always route there; the SDK stays available for static props only.
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        value = str(item)
        if value not in sys.path:
            sys.path.insert(0, value)


def _model(*, skinned: bool, animated: bool):
    from src.core.geometry import model_data as md

    root = md.ModelNode(name="root", flags=int(md.NodeFlags.HEADER))
    mesh_flags = int(md.NodeFlags.HEADER) | int(md.NodeFlags.MESH)
    if skinned:
        mesh_flags |= int(md.NodeFlags.SKIN)
    mesh = md.ModelNode(
        name="body_g",
        flags=mesh_flags,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[(0, 1, 2)],
    )
    mesh.parent = root
    root.children.append(mesh)
    model = md.KotorModel(name="gatecheck", root_node=root)
    if animated:
        model.animations = [md.Animation(name="walk", length=1.0)]
    return model


def _run_export(monkeypatch, tmp_path, model, *, compatibility_profile="standard"):
    from src.converters import mesh_converter

    calls = {"sdk": 0, "ascii": 0}

    def fake_sdk(self, target_model, fbx_path, fbx):
        calls["sdk"] += 1
        return True

    def fake_ascii(
        self,
        target_model,
        fbx_path,
        base_skeleton_model=None,
        texture_paths=None,
        compatibility_profile="standard",
    ):
        calls["ascii"] += 1
        calls["profile"] = compatibility_profile
        Path(fbx_path).write_text("; FBX 7.4 ASCII stub", encoding="ascii")
        return True

    monkeypatch.setattr(mesh_converter.FBXExporter, "_export_fbx_sdk", fake_sdk)
    monkeypatch.setattr(mesh_converter.FBXExporter, "_export_fbx_ascii", fake_ascii)
    # Make `import fbx` succeed so the SDK branch is genuinely reachable.
    monkeypatch.setitem(sys.modules, "fbx", types.ModuleType("fbx"))
    monkeypatch.setitem(sys.modules, "pyassimp", None)  # force ImportError path
    out = tmp_path / f"{model.name}.fbx"
    ok = mesh_converter.FBXExporter().export(
        model,
        str(out),
        export_rigging=False,
        export_manifest=False,
        compatibility_profile=compatibility_profile,
    )
    return ok, calls


def test_skinned_model_routes_to_ascii_writer(monkeypatch, tmp_path) -> None:
    _configure_native_python_roots()
    ok, calls = _run_export(monkeypatch, tmp_path, _model(skinned=True, animated=False))
    assert ok
    assert calls["sdk"] == 0
    assert calls["ascii"] == 1


def test_animated_model_routes_to_ascii_writer(monkeypatch, tmp_path) -> None:
    _configure_native_python_roots()
    ok, calls = _run_export(monkeypatch, tmp_path, _model(skinned=False, animated=True))
    assert ok
    assert calls["sdk"] == 0
    assert calls["ascii"] == 1


def test_static_model_still_uses_sdk_when_available(monkeypatch, tmp_path) -> None:
    _configure_native_python_roots()
    ok, calls = _run_export(monkeypatch, tmp_path, _model(skinned=False, animated=False))
    assert ok
    assert calls["sdk"] == 1
    assert calls["ascii"] == 0


def test_static_unity_profile_bypasses_incomplete_sdk_writer(monkeypatch, tmp_path) -> None:
    _configure_native_python_roots()
    ok, calls = _run_export(
        monkeypatch,
        tmp_path,
        _model(skinned=False, animated=False),
        compatibility_profile="unity",
    )
    assert ok
    assert calls["sdk"] == 0
    assert calls["ascii"] == 1
    assert calls["profile"] == "unity"


def test_static_unreal_profile_bypasses_incomplete_sdk_writer(monkeypatch, tmp_path) -> None:
    _configure_native_python_roots()
    ok, calls = _run_export(
        monkeypatch,
        tmp_path,
        _model(skinned=False, animated=False),
        compatibility_profile="unreal",
    )
    assert ok
    assert calls["sdk"] == 0
    assert calls["ascii"] == 1
    assert calls["profile"] == "unreal"
