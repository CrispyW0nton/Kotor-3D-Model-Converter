"""Tests for the optional FBX backend registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.retargeting import fbx_backend
from src.core.retargeting.fbx_backend import (
    AutodeskSDKFBXImporter,
    BlenderFBXImporter,
    FBXBackendFactory,
    FBXBackendType,
)


class _FakeFbxManager:
    def __init__(self) -> None:
        self.destroyed = False

    def GetVersion(self) -> str:
        return "2020.3.4"

    def Destroy(self) -> None:
        self.destroyed = True


class _FakeFbxModule:
    class FbxManager:
        @staticmethod
        def Create() -> _FakeFbxManager:
            return _FakeFbxManager()


def test_backend_type_from_string_accepts_documented_values() -> None:
    assert FBXBackendFactory.backend_type_from_string("autodesk_sdk") is FBXBackendType.AUTODESK_SDK
    assert FBXBackendFactory.backend_type_from_string("sdk") is FBXBackendType.AUTODESK_SDK
    assert FBXBackendFactory.backend_type_from_string("blender") is FBXBackendType.BLENDER_HEADLESS
    assert FBXBackendFactory.backend_type_from_string(None) is FBXBackendType.BLENDER_HEADLESS


def test_blender_backend_info_uses_existing_executable_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        fbx_backend,
        "find_blender_executable",
        lambda explicit=None: Path(r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"),
    )
    monkeypatch.setattr(fbx_backend, "blender_version", lambda _exe: "Blender 4.2.0\nbuild date")

    info = BlenderFBXImporter().get_backend_info()

    assert info.name == "Blender Headless"
    assert info.available is True
    assert info.requirements_met is True
    assert info.version == "Blender 4.2.0"
    assert info.sdk_used == "Blender built-in FBX importer/exporter"


def test_blender_backend_delegates_to_production_source_clip_importer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, object]] = []
    expected = object()

    monkeypatch.setattr(BlenderFBXImporter, "is_available", lambda self: True)

    def fake_import(path: str, *, backend=None):
        calls.append((path, backend))
        return expected

    monkeypatch.setattr(fbx_backend, "import_ue_fbx_animation_clip", fake_import)

    result = BlenderFBXImporter().import_animation(Path("source.fbx"))

    assert result is expected
    assert calls == [("source.fbx", None)]


def test_autodesk_backend_reports_missing_module_without_raising() -> None:
    importer = AutodeskSDKFBXImporter(module_loader=lambda: (_ for _ in ()).throw(ImportError("No module named fbx")))

    info = importer.get_backend_info()

    assert importer.is_available() is False
    assert info.name == "Autodesk FBX SDK"
    assert info.available is False
    assert info.requirements_met is False
    assert "FBX module import failed" in (info.error_message or "")
    assert "No module named fbx" in (info.error_message or "")


def test_autodesk_backend_probe_records_sdk_version() -> None:
    importer = AutodeskSDKFBXImporter(module_loader=lambda: _FakeFbxModule)

    info = importer.get_backend_info()

    assert importer.is_available() is True
    assert info.available is True
    assert info.version == "2020.3.4"
    assert info.sdk_used == "Autodesk FBX SDK Python Bindings"

    with pytest.raises(NotImplementedError, match="pending implementation"):
        importer.import_animation(Path("source.fbx"))


def test_factory_rejects_unavailable_autodesk_without_implicit_blender_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MissingAutodesk:
        def is_available(self) -> bool:
            return False

        def get_backend_info(self):
            return type("Info", (), {"error_message": "missing sdk"})()

    class AvailableBlender:
        def is_available(self) -> bool:
            return True

    monkeypatch.setattr(fbx_backend, "AutodeskSDKFBXImporter", MissingAutodesk)
    monkeypatch.setattr(fbx_backend, "BlenderFBXImporter", AvailableBlender)

    with pytest.raises(OSError, match="missing sdk"):
        FBXBackendFactory.get_importer(FBXBackendType.AUTODESK_SDK)


def test_factory_can_use_blender_fallback_when_explicitly_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MissingAutodesk:
        def is_available(self) -> bool:
            return False

        def get_backend_info(self):
            return type("Info", (), {"error_message": "missing sdk"})()

    class AvailableBlender:
        def is_available(self) -> bool:
            return True

    monkeypatch.setattr(fbx_backend, "AutodeskSDKFBXImporter", MissingAutodesk)
    monkeypatch.setattr(fbx_backend, "BlenderFBXImporter", AvailableBlender)

    importer = FBXBackendFactory.get_importer(FBXBackendType.AUTODESK_SDK, allow_fallback=True)

    assert isinstance(importer, AvailableBlender)
