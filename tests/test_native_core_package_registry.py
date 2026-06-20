from __future__ import annotations

import json
from pathlib import Path

import pytest

import src.adapters.native_core.package_registry as package_registry
from src.adapters.native_core.package_registry import (
    NATIVE_CORE_DIAGNOSTICS_PACKAGE,
    NATIVE_CORE_MATH_PACKAGE,
    NATIVE_CORE_PACKAGE,
    RENDERER_CONTRACTS_PACKAGE,
    RENDERER_D3D12_PACKAGE,
    RENDERER_MODERNGL_PACKAGE,
    RENDERER_NULL_PACKAGE,
    RENDERER_PYGFX_PACKAGE,
    RUNTIME_SHARED_CONTRACTS_PACKAGE,
    RUNTIME_SHARED_DESCRIPTORS_PACKAGE,
    RUNTIME_SHARED_RESOURCES_PACKAGE,
    TOOLS_BODY_ATTACHMENT_SYSTEM_PACKAGE,
    TOOLS_CAMERA_PACKAGE,
    TOOLS_CHARACTER_BUILDER_PACKAGE,
    TOOLS_CONTENT_BROWSER_PACKAGE,
    TOOLS_EXPORT_PACKAGE,
    TOOLS_LIGHTING_PACKAGE,
    TOOLS_MODULE_MESHES_PACKAGE,
    TOOLS_NODES_SKELETON_BROWSER_PACKAGE,
    TOOLS_PIVOT_CONTROLS_PACKAGE,
    TOOLS_PROPERTIES_PACKAGE,
    TOOLS_RESOURCE_BROWSER_PACKAGE,
    TOOLS_RETARGETING_PACKAGE,
    TOOLS_SCENE_INFORMATION_PACKAGE,
    TOOLS_SEQUENCE_EDITOR_PACKAGE,
    TOOLS_SPRITE_MATERIALS_PACKAGE,
    TOOLS_TWO_DA_BROWSER_PACKAGE,
    WINDOWS_ANIMATION_RETARGET_WORKBENCH_PACKAGE,
    WINDOWS_LEGACY_RIGGING_WINDOW_PACKAGE,
    WINDOWS_LEVEL_EDITOR_PACKAGE,
    WINDOWS_MAIN_WINDOW_PACKAGE,
    WINDOWS_UNREAL_ANIMATOR_WINDOW_PACKAGE,
    NativePackageSpec,
    NativePackageStatus,
    query_native_package_status,
)


ROOT = Path(__file__).resolve().parents[1]
MODULE_MANIFEST = ROOT / "native" / "GhostRigger.NativeModulePackages.json"


class _FakeNativeExport:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.restype = None

    def __call__(self) -> bytes:
        return self.payload


class _FakeDll:
    gr_renderer_d3d12_version = _FakeNativeExport(b"0.1.0")
    gr_renderer_d3d12_capabilities_json = _FakeNativeExport(
        b'{"name":"GhostRigger.Core.Rendering","renderer_backend":true}'
    )


@pytest.mark.parametrize(
    ("spec", "expected_name", "expected_dll"),
    [
        (NATIVE_CORE_PACKAGE, "GhostRigger.Native.Core.Foundation", "GhostRigger.Native.Core.Foundation.dll"),
        (NATIVE_CORE_DIAGNOSTICS_PACKAGE, "GhostRigger.Native.Core.Foundation", "GhostRigger.Native.Core.Foundation.dll"),
        (NATIVE_CORE_MATH_PACKAGE, "GhostRigger.Native.Core.Foundation", "GhostRigger.Native.Core.Foundation.dll"),
        (RUNTIME_SHARED_CONTRACTS_PACKAGE, "GhostRigger.Runtime.Shared", "GhostRigger.Runtime.Shared.dll"),
        (RUNTIME_SHARED_DESCRIPTORS_PACKAGE, "GhostRigger.Runtime.Shared", "GhostRigger.Runtime.Shared.dll"),
        (RUNTIME_SHARED_RESOURCES_PACKAGE, "GhostRigger.Runtime.Shared", "GhostRigger.Runtime.Shared.dll"),
        (RENDERER_CONTRACTS_PACKAGE, "GhostRigger.Core.Rendering", "GhostRigger.Core.Rendering.dll"),
        (RENDERER_NULL_PACKAGE, "GhostRigger.Core.Rendering", "GhostRigger.Core.Rendering.dll"),
        (RENDERER_D3D12_PACKAGE, "GhostRigger.Core.Rendering", "GhostRigger.Core.Rendering.dll"),
        (RENDERER_MODERNGL_PACKAGE, "GhostRigger.Core.Rendering", "GhostRigger.Core.Rendering.dll"),
        (RENDERER_PYGFX_PACKAGE, "GhostRigger.Core.Rendering", "GhostRigger.Core.Rendering.dll"),
        (TOOLS_RETARGETING_PACKAGE, "GhostRigger.Core.Tools", "GhostRigger.Core.Tools.dll"),
        (TOOLS_EXPORT_PACKAGE, "GhostRigger.Core.Tools", "GhostRigger.Core.Tools.dll"),
        (TOOLS_CHARACTER_BUILDER_PACKAGE, "GhostRigger.Core.Tools", "GhostRigger.Core.Tools.dll"),
        (TOOLS_CONTENT_BROWSER_PACKAGE, "GhostRigger.Core.Tools", "GhostRigger.Core.Tools.dll"),
        (TOOLS_RESOURCE_BROWSER_PACKAGE, "GhostRigger.Core.Tools", "GhostRigger.Core.Tools.dll"),
        (TOOLS_TWO_DA_BROWSER_PACKAGE, "GhostRigger.Core.Tools", "GhostRigger.Core.Tools.dll"),
        (TOOLS_SCENE_INFORMATION_PACKAGE, "GhostRigger.Core.Tools", "GhostRigger.Core.Tools.dll"),
        (TOOLS_PROPERTIES_PACKAGE, "GhostRigger.Core.Tools", "GhostRigger.Core.Tools.dll"),
        (TOOLS_LIGHTING_PACKAGE, "GhostRigger.Core.Tools", "GhostRigger.Core.Tools.dll"),
        (TOOLS_CAMERA_PACKAGE, "GhostRigger.Core.Tools", "GhostRigger.Core.Tools.dll"),
        (TOOLS_MODULE_MESHES_PACKAGE, "GhostRigger.Core.Tools", "GhostRigger.Core.Tools.dll"),
        (TOOLS_BODY_ATTACHMENT_SYSTEM_PACKAGE, "GhostRigger.Core.Tools", "GhostRigger.Core.Tools.dll"),
        (TOOLS_NODES_SKELETON_BROWSER_PACKAGE, "GhostRigger.Core.Tools", "GhostRigger.Core.Tools.dll"),
        (TOOLS_SPRITE_MATERIALS_PACKAGE, "GhostRigger.Core.Tools", "GhostRigger.Core.Tools.dll"),
        (TOOLS_PIVOT_CONTROLS_PACKAGE, "GhostRigger.Core.Tools", "GhostRigger.Core.Tools.dll"),
        (TOOLS_SEQUENCE_EDITOR_PACKAGE, "GhostRigger.Core.Tools", "GhostRigger.Core.Tools.dll"),
        (WINDOWS_MAIN_WINDOW_PACKAGE, "GhostRigger.Core.GUI.Display", "GhostRigger.Core.GUI.Display.dll"),
        (WINDOWS_LEVEL_EDITOR_PACKAGE, "GhostRigger.Core.Tools", "GhostRigger.Core.Tools.dll"),
        (WINDOWS_ANIMATION_RETARGET_WORKBENCH_PACKAGE, "GhostRigger.Core.Tools", "GhostRigger.Core.Tools.dll"),
        (WINDOWS_LEGACY_RIGGING_WINDOW_PACKAGE, "GhostRigger.Core.Tools", "GhostRigger.Core.Tools.dll"),
        (WINDOWS_UNREAL_ANIMATOR_WINDOW_PACKAGE, "GhostRigger.Core.Tools", "GhostRigger.Core.Tools.dll"),
    ],
)
def test_registry_specs_use_aggregate_dll_owners(
    spec: NativePackageSpec,
    expected_name: str,
    expected_dll: str,
    tmp_path: Path,
) -> None:
    assert spec.name == expected_name
    assert spec.dll_name == expected_dll
    assert not spec.name.endswith(".vcxproj")
    assert spec.dll_name.endswith(".dll")

    status = query_native_package_status(spec, [tmp_path])

    assert isinstance(status, NativePackageStatus)
    assert status.name == expected_name
    assert status.available is False


def test_query_native_package_status_decodes_aggregate_capabilities(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dll_path = tmp_path / RENDERER_D3D12_PACKAGE.dll_name
    dll_path.write_bytes(b"")
    monkeypatch.setattr(package_registry, "_load_library", lambda _path: _FakeDll())

    status = query_native_package_status(RENDERER_D3D12_PACKAGE, [tmp_path])

    assert status.available is True
    assert status.name == "GhostRigger.Core.Rendering"
    assert status.version == "0.1.0"
    assert status.capabilities == {
        "name": "GhostRigger.Core.Rendering",
        "renderer_backend": True,
    }
    assert status.path == str(dll_path)


def test_python_module_specs_follow_collapsed_manifest_order() -> None:
    manifest_entries = json.loads(MODULE_MANIFEST.read_text(encoding="utf-8"))
    specs = package_registry.python_module_package_specs()

    assert tuple(spec.name for spec in specs) == tuple(
        entry["name"] for entry in manifest_entries
    )
    assert tuple(spec.version_export for spec in specs) == tuple(
        f"gr_{entry['symbol_prefix']}_version" for entry in manifest_entries
    )
    assert all(spec.dll_name == f"{spec.name}.dll" for spec in specs)
    assert all(not spec.name.endswith(".vcxproj") for spec in specs)
