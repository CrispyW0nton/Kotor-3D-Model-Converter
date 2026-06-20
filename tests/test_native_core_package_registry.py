from __future__ import annotations

from pathlib import Path

import src.adapters.native_core.package_registry as package_registry
from src.adapters.native_core.package_registry import (
    NATIVE_CORE_DIAGNOSTICS_PACKAGE,
    NATIVE_CORE_MATH_PACKAGE,
    NATIVE_CORE_PACKAGE,
    RENDERER_CONTRACTS_PACKAGE,
    RENDERER_D3D12_GUARDED_METADATA_CAPABILITIES,
    RENDERER_D3D12_PACKAGE,
    RENDERER_MODERNGL_PACKAGE,
    RENDERER_NULL_PACKAGE,
    RENDERER_PYGFX_PACKAGE,
    RUNTIME_SHARED_CONTRACTS_PACKAGE,
    RUNTIME_SHARED_DESCRIPTORS_PACKAGE,
    RUNTIME_SHARED_RESOURCES_PACKAGE,
    TOOLS_BODY_ATTACHMENT_SYSTEM_PACKAGE,
    TOOLS_CHARACTER_BUILDER_PACKAGE,
    TOOLS_CAMERA_PACKAGE,
    TOOLS_CONTENT_BROWSER_PACKAGE,
    TOOLS_EXPORT_PACKAGE,
    TOOLS_LIGHTING_PACKAGE,
    TOOLS_MODULE_MESHES_PACKAGE,
    TOOLS_NODES_SKELETON_BROWSER_PACKAGE,
    TOOLS_PIVOT_CONTROLS_PACKAGE,
    TOOLS_PROPERTIES_PACKAGE,
    TOOLS_RETARGETING_PACKAGE,
    TOOLS_RESOURCE_BROWSER_PACKAGE,
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
    query_native_core_diagnostics_status,
    query_native_core_math_status,
    query_native_core_status,
    query_native_package_status,
    query_renderer_contracts_status,
    query_renderer_d3d12_status,
    query_renderer_moderngl_status,
    query_renderer_null_status,
    query_renderer_pygfx_status,
    query_runtime_shared_contracts_status,
    query_runtime_shared_descriptors_status,
    query_runtime_shared_resources_status,
    query_tools_body_attachment_system_status,
    query_tools_camera_status,
    query_tools_character_builder_status,
    query_tools_content_browser_status,
    query_tools_export_status,
    query_tools_lighting_status,
    query_tools_module_meshes_status,
    query_tools_nodes_skeleton_browser_status,
    query_tools_pivot_controls_status,
    query_tools_properties_status,
    query_tools_resource_browser_status,
    query_tools_retargeting_status,
    query_tools_scene_information_status,
    query_tools_sequence_editor_status,
    query_tools_sprite_materials_status,
    query_tools_two_da_browser_status,
    query_windows_animation_retarget_workbench_status,
    query_windows_legacy_rigging_window_status,
    query_windows_level_editor_status,
    query_windows_main_window_status,
    query_windows_unreal_animator_window_status,
    renderer_d3d12_guarded_metadata_capabilities,
)


class _FakeNativeExport:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.restype = None

    def __call__(self) -> bytes:
        return self.payload


class _FakeRendererD3D12Dll:
    gr_renderer_d3d12_version = _FakeNativeExport(b"0.1.0")
    gr_renderer_d3d12_capabilities_json = _FakeNativeExport(
        (
            b'{"name":"GhostRigger.Core.Rendering.Backends.D3D12","version":"0.1.0",'
            b'"draw_submission_enabled":false,'
            b'"guarded_metadata_capabilities":['
            b'"descriptor_allocator_readiness",'
            b'"command_list_readiness",'
            b'"surface_swap_chain_readiness",'
            b'"render_target_metadata",'
            b'"barrier_clear_pass_metadata",'
            b'"command_recording_dry_run_frame",'
            b'"guarded_command_recording_diagnostics",'
            b'"no_draw_execution_fence_diagnostics",'
            b'"present_readiness_metadata",'
            b'"guarded_swap_chain_creation_diagnostics",'
            b'"guarded_back_buffer_rtv_diagnostics",'
            b'"guarded_barrier_clear_recording_diagnostics",'
            b'"guarded_clear_pass_execution_fence_diagnostics",'
            b'"post_clear_present_readiness_diagnostics",'
            b'"guarded_present_call_diagnostics",'
            b'"post_present_frame_accounting_diagnostics",'
            b'"draw_list_readiness_metadata",'
            b'"resource_binding_readiness_metadata",'
            b'"pipeline_state_readiness_metadata",'
            b'"guarded_shader_bytecode_metadata",'
            b'"shader_reflection_input_layout_metadata",'
            b'"guarded_root_signature_metadata",'
            b'"guarded_pipeline_state_object_metadata",'
            b'"guarded_draw_command_recording_metadata",'
            b'"guarded_draw_submission_readiness_metadata",'
            b'"guarded_post_draw_frame_accounting_readiness_metadata"]}'
        )
    )


class _FakeRendererModernGLDll:
    gr_renderer_moderngl_version = _FakeNativeExport(b"0.1.0")
    gr_renderer_moderngl_capabilities_json = _FakeNativeExport(
        (
            b'{"name":"GhostRigger.Core.Rendering.Backends.ModernGL","version":"0.1.0",'
            b'"renderer_backend":true,"backend":"moderngl",'
            b'"contract_version":"0.1.0","python_adapter_required":true,'
            b'"native_device_owner":false,"draw_submission_enabled":false}'
        )
    )


class _FakeRendererPyGFXDll:
    gr_renderer_pygfx_version = _FakeNativeExport(b"0.1.0")
    gr_renderer_pygfx_capabilities_json = _FakeNativeExport(
        (
            b'{"name":"GhostRigger.Core.Rendering.Backends.PyGFX","version":"0.1.0",'
            b'"renderer_backend":true,"backend":"pygfx",'
            b'"contract_version":"0.1.0","python_adapter_required":true,'
            b'"native_device_owner":false,"draw_submission_enabled":false}'
        )
    )


class _FakeToolsRetargetingDll:
    gr_tools_retargeting_version = _FakeNativeExport(b"0.1.0")
    gr_tools_retargeting_capabilities_json = _FakeNativeExport(
        (
            b'{"name":"GhostRigger.Core.Tools.Retargeting","version":"0.1.0",'
            b'"tool_package":true,"owner_surface":"Retarget Workbench",'
            b'"bridge_method":"C ABI DLL","diagnostic_only":true,'
            b'"native_solve_enabled":false,"python_fallback_required":true}'
        )
    )


class _FakeToolsExportDll:
    gr_tools_export_version = _FakeNativeExport(b"0.1.0")
    gr_tools_export_capabilities_json = _FakeNativeExport(
        (
            b'{"name":"GhostRigger.Core.Tools.Export","version":"0.1.0",'
            b'"tool_package":true,"owner_surface":"Export and validation workflow",'
            b'"bridge_method":"C ABI DLL","diagnostic_only":true,'
            b'"native_write_enabled":false,"python_fallback_required":true}'
        )
    )


class _FakeToolsCharacterBuilderDll:
    gr_tools_character_builder_version = _FakeNativeExport(b"0.1.0")
    gr_tools_character_builder_capabilities_json = _FakeNativeExport(
        (
            b'{"name":"GhostRigger.Core.Tools.CharacterBuilder","version":"0.1.0",'
            b'"tool_package":true,"owner_surface":"Character Studio",'
            b'"bridge_method":"C ABI DLL","diagnostic_only":true,'
            b'"native_autofit_enabled":false,"python_fallback_required":true}'
        )
    )


class _FakeWindowsMainWindowDll:
    gr_windows_main_window_version = _FakeNativeExport(b"0.1.0")
    gr_windows_main_window_capabilities_json = _FakeNativeExport(
        (
            b'{"name":"GhostRigger.Core.GUI.Display.Shell.Main","version":"0.1.0",'
            b'"window_package":true,"owner_surface":"Main window composition shell",'
            b'"bridge_method":"C ABI DLL","diagnostic_only":true,'
            b'"native_shell_enabled":false,"python_fallback_required":true}'
        )
    )


def test_native_core_status_reports_missing_package(tmp_path: Path) -> None:
    status = query_native_core_status([tmp_path])

    assert isinstance(status, NativePackageStatus)
    assert status.name == "GhostRigger.Native.Core.Foundation"
    assert status.available is False
    assert "not found" in status.reason or "Windows native package" in status.reason


def test_generic_native_package_status_reports_package_specific_missing_dll(tmp_path: Path) -> None:
    spec = NativePackageSpec(
        name="GhostRigger.Runtime.Shared.Example",
        dll_name="GhostRigger.Runtime.Shared.Example.dll",
        env_var="GHOSTRIGGER_RUNTIME_SHARED_EXAMPLE",
    )

    status = query_native_package_status(spec, [tmp_path])

    assert status.name == "GhostRigger.Runtime.Shared.Example"
    assert status.available is False
    assert (
        "GhostRigger.Runtime.Shared.Example.dll was not found." in status.reason
        or "Windows native package" in status.reason
    )


def test_runtime_shared_contracts_status_uses_shared_registry_path(tmp_path: Path) -> None:
    status = query_runtime_shared_contracts_status([tmp_path])

    assert status.name == "GhostRigger.Runtime.Shared.Contracts"
    assert status.available is False
    assert (
        "GhostRigger.Runtime.Shared.Contracts.dll was not found." in status.reason
        or "Windows native package" in status.reason
    )


def test_runtime_shared_descriptors_status_uses_shared_registry_path(tmp_path: Path) -> None:
    status = query_runtime_shared_descriptors_status([tmp_path])

    assert status.name == "GhostRigger.Runtime.Shared.Descriptors"
    assert status.available is False
    assert (
        "GhostRigger.Runtime.Shared.Descriptors.dll was not found." in status.reason
        or "Windows native package" in status.reason
    )


def test_runtime_shared_resources_status_uses_shared_registry_path(tmp_path: Path) -> None:
    status = query_runtime_shared_resources_status([tmp_path])

    assert status.name == "GhostRigger.Runtime.Shared.Resources"
    assert status.available is False
    assert (
        "GhostRigger.Runtime.Shared.Resources.dll was not found." in status.reason
        or "Windows native package" in status.reason
    )


def test_renderer_contracts_status_uses_shared_registry_path(tmp_path: Path) -> None:
    status = query_renderer_contracts_status([tmp_path])

    assert status.name == "GhostRigger.Core.Rendering.Contracts"
    assert status.available is False
    assert (
        "GhostRigger.Core.Rendering.Contracts.dll was not found." in status.reason
        or "Windows native package" in status.reason
    )


def test_renderer_null_status_uses_shared_registry_path(tmp_path: Path) -> None:
    status = query_renderer_null_status([tmp_path])

    assert status.name == "GhostRigger.Core.Rendering.Backends.Null"
    assert status.available is False
    assert (
        "GhostRigger.Core.Rendering.Backends.Null.dll was not found." in status.reason
        or "Windows native package" in status.reason
    )


def test_renderer_d3d12_status_uses_shared_registry_path(tmp_path: Path) -> None:
    status = query_renderer_d3d12_status([tmp_path])

    assert status.name == "GhostRigger.Core.Rendering.Backends.D3D12"
    assert status.available is False
    assert (
        "GhostRigger.Core.Rendering.Backends.D3D12.dll was not found." in status.reason
        or "Windows native package" in status.reason
    )


def test_renderer_moderngl_status_uses_shared_registry_path(tmp_path: Path) -> None:
    status = query_renderer_moderngl_status([tmp_path])

    assert status.name == "GhostRigger.Core.Rendering.Backends.ModernGL"
    assert status.available is False
    assert (
        "GhostRigger.Core.Rendering.Backends.ModernGL.dll was not found." in status.reason
        or "Windows native package" in status.reason
    )


def test_renderer_pygfx_status_uses_shared_registry_path(tmp_path: Path) -> None:
    status = query_renderer_pygfx_status([tmp_path])

    assert status.name == "GhostRigger.Core.Rendering.Backends.PyGFX"
    assert status.available is False
    assert (
        "GhostRigger.Core.Rendering.Backends.PyGFX.dll was not found." in status.reason
        or "Windows native package" in status.reason
    )


def test_tools_retargeting_status_uses_shared_registry_path(tmp_path: Path) -> None:
    status = query_tools_retargeting_status([tmp_path])

    assert status.name == "GhostRigger.Core.Tools.Retargeting"
    assert status.available is False
    assert (
        "GhostRigger.Core.Tools.Retargeting.dll was not found." in status.reason
        or "Windows native package" in status.reason
    )


def test_tools_export_status_uses_shared_registry_path(tmp_path: Path) -> None:
    status = query_tools_export_status([tmp_path])

    assert status.name == "GhostRigger.Core.Tools.Export"
    assert status.available is False
    assert (
        "GhostRigger.Core.Tools.Export.dll was not found." in status.reason
        or "Windows native package" in status.reason
    )


def test_tools_character_builder_status_uses_shared_registry_path(tmp_path: Path) -> None:
    status = query_tools_character_builder_status([tmp_path])

    assert status.name == "GhostRigger.Core.Tools.CharacterBuilder"
    assert status.available is False
    assert (
        "GhostRigger.Core.Tools.CharacterBuilder.dll was not found." in status.reason
        or "Windows native package" in status.reason
    )


def test_browser_tool_statuses_use_shared_registry_path(tmp_path: Path) -> None:
    cases = (
        (query_tools_content_browser_status, "GhostRigger.Core.Tools.ContentBrowser"),
        (query_tools_resource_browser_status, "GhostRigger.Core.Tools.ResourceBrowser"),
        (query_tools_two_da_browser_status, "GhostRigger.Core.Tools.TwoDABrowser"),
    )

    for query_status, package_name in cases:
        status = query_status([tmp_path])
        assert status.name == package_name
        assert status.available is False
        assert f"{package_name}.dll was not found." in status.reason or "Windows native package" in status.reason


def test_scene_workbench_tool_statuses_use_shared_registry_path(tmp_path: Path) -> None:
    cases = (
        (query_tools_scene_information_status, "GhostRigger.Core.Tools.SceneInformation"),
        (query_tools_properties_status, "GhostRigger.Core.Tools.Properties"),
        (query_tools_lighting_status, "GhostRigger.Core.Tools.Lighting"),
        (query_tools_camera_status, "GhostRigger.Core.Tools.Camera"),
        (query_tools_module_meshes_status, "GhostRigger.Core.Tools.ModuleMeshes"),
    )

    for query_status, package_name in cases:
        status = query_status([tmp_path])
        assert status.name == package_name
        assert status.available is False
        assert f"{package_name}.dll was not found." in status.reason or "Windows native package" in status.reason


def test_final_phase_one_tool_statuses_use_shared_registry_path(tmp_path: Path) -> None:
    cases = (
        (query_tools_body_attachment_system_status, "GhostRigger.Core.Tools.BAS"),
        (query_tools_nodes_skeleton_browser_status, "GhostRigger.Core.Tools.NodeSkeletonBrowser"),
        (query_tools_sprite_materials_status, "GhostRigger.Core.Tools.SpriteMaterials"),
        (query_tools_pivot_controls_status, "GhostRigger.Core.Tools.PivotControls"),
        (query_tools_sequence_editor_status, "GhostRigger.Core.Tools.SequenceEditor"),
    )

    for query_status, package_name in cases:
        status = query_status([tmp_path])
        assert status.name == package_name
        assert status.available is False
        assert f"{package_name}.dll was not found." in status.reason or "Windows native package" in status.reason


def test_windows_main_window_status_uses_shared_registry_path(tmp_path: Path) -> None:
    status = query_windows_main_window_status([tmp_path])

    assert status.name == "GhostRigger.Core.GUI.Display.Shell.Main"
    assert status.available is False
    assert (
        "GhostRigger.Core.GUI.Display.Shell.Main.dll was not found." in status.reason
        or "Windows native package" in status.reason
    )


def test_extra_window_statuses_use_shared_registry_path(tmp_path: Path) -> None:
    cases = (
        (query_windows_level_editor_status, "GhostRigger.Core.Tools.ModuleEditor"),
        (
            query_windows_animation_retarget_workbench_status,
            "GhostRigger.Core.Tools.Retargeting.Workbench",
        ),
        (query_windows_legacy_rigging_window_status, "GhostRigger.Core.Tools.Rigging"),
        (query_windows_unreal_animator_window_status, "GhostRigger.Core.Tools.UnrealAnimator"),
    )

    for query_status, package_name in cases:
        status = query_status([tmp_path])
        assert status.name == package_name
        assert status.available is False
        assert f"{package_name}.dll was not found." in status.reason or "Windows native package" in status.reason


def test_native_core_diagnostics_status_uses_shared_registry_path(tmp_path: Path) -> None:
    status = query_native_core_diagnostics_status([tmp_path])

    assert status.name == "GhostRigger.Native.Core.Diagnostics"
    assert status.available is False
    assert (
        "GhostRigger.Native.Core.Diagnostics.dll was not found." in status.reason
        or "Windows native package" in status.reason
    )


def test_native_core_math_status_uses_shared_registry_path(tmp_path: Path) -> None:
    status = query_native_core_math_status([tmp_path])

    assert status.name == "GhostRigger.Native.Core.Math"
    assert status.available is False
    assert (
        "GhostRigger.Native.Core.Math.dll was not found." in status.reason
        or "Windows native package" in status.reason
    )


def test_native_core_package_registry_exports_stable_status_fields() -> None:
    status = NativePackageStatus(
        name="GhostRigger.Native.Core.Foundation",
        available=True,
        version="0.1.0",
        capabilities={"shared_handles": True},
        path="native.dll",
    )

    assert status.name == "GhostRigger.Native.Core.Foundation"
    assert status.available is True
    assert status.version == "0.1.0"
    assert status.capabilities == {"shared_handles": True}
    assert status.path == "native.dll"


def test_native_core_package_spec_names_current_core_contract() -> None:
    assert NATIVE_CORE_PACKAGE.name == "GhostRigger.Native.Core.Foundation"
    assert NATIVE_CORE_PACKAGE.dll_name == "GhostRigger.Native.Core.Foundation.dll"
    assert NATIVE_CORE_PACKAGE.env_var == "GHOSTRIGGER_NATIVE_CORE"
    assert NATIVE_CORE_PACKAGE.version_export == "gr_native_core_version"
    assert NATIVE_CORE_PACKAGE.capabilities_export == "gr_native_core_capabilities_json"


def test_native_core_diagnostics_package_spec_names_current_contract() -> None:
    assert NATIVE_CORE_DIAGNOSTICS_PACKAGE.name == "GhostRigger.Native.Core.Diagnostics"
    assert NATIVE_CORE_DIAGNOSTICS_PACKAGE.dll_name == "GhostRigger.Native.Core.Diagnostics.dll"
    assert NATIVE_CORE_DIAGNOSTICS_PACKAGE.env_var == "GHOSTRIGGER_NATIVE_CORE_DIAGNOSTICS"
    assert NATIVE_CORE_DIAGNOSTICS_PACKAGE.version_export == "gr_native_core_diagnostics_version"
    assert (
        NATIVE_CORE_DIAGNOSTICS_PACKAGE.capabilities_export
        == "gr_native_core_diagnostics_capabilities_json"
    )


def test_native_core_math_package_spec_names_current_contract() -> None:
    assert NATIVE_CORE_MATH_PACKAGE.name == "GhostRigger.Native.Core.Math"
    assert NATIVE_CORE_MATH_PACKAGE.dll_name == "GhostRigger.Native.Core.Math.dll"
    assert NATIVE_CORE_MATH_PACKAGE.env_var == "GHOSTRIGGER_NATIVE_CORE_MATH"
    assert NATIVE_CORE_MATH_PACKAGE.version_export == "gr_native_core_math_version"
    assert NATIVE_CORE_MATH_PACKAGE.capabilities_export == "gr_native_core_math_capabilities_json"


def test_runtime_shared_contracts_package_spec_names_current_contract() -> None:
    assert RUNTIME_SHARED_CONTRACTS_PACKAGE.name == "GhostRigger.Runtime.Shared.Contracts"
    assert RUNTIME_SHARED_CONTRACTS_PACKAGE.dll_name == "GhostRigger.Runtime.Shared.Contracts.dll"
    assert RUNTIME_SHARED_CONTRACTS_PACKAGE.env_var == "GHOSTRIGGER_RUNTIME_SHARED_CONTRACTS"
    assert RUNTIME_SHARED_CONTRACTS_PACKAGE.version_export == "gr_runtime_shared_contracts_version"
    assert (
        RUNTIME_SHARED_CONTRACTS_PACKAGE.capabilities_export
        == "gr_runtime_shared_contracts_capabilities_json"
    )


def test_runtime_shared_descriptors_package_spec_names_current_contract() -> None:
    assert RUNTIME_SHARED_DESCRIPTORS_PACKAGE.name == "GhostRigger.Runtime.Shared.Descriptors"
    assert RUNTIME_SHARED_DESCRIPTORS_PACKAGE.dll_name == "GhostRigger.Runtime.Shared.Descriptors.dll"
    assert RUNTIME_SHARED_DESCRIPTORS_PACKAGE.env_var == "GHOSTRIGGER_RUNTIME_SHARED_DESCRIPTORS"
    assert RUNTIME_SHARED_DESCRIPTORS_PACKAGE.version_export == "gr_runtime_shared_descriptors_version"
    assert (
        RUNTIME_SHARED_DESCRIPTORS_PACKAGE.capabilities_export
        == "gr_runtime_shared_descriptors_capabilities_json"
    )


def test_runtime_shared_resources_package_spec_names_current_contract() -> None:
    assert RUNTIME_SHARED_RESOURCES_PACKAGE.name == "GhostRigger.Runtime.Shared.Resources"
    assert RUNTIME_SHARED_RESOURCES_PACKAGE.dll_name == "GhostRigger.Runtime.Shared.Resources.dll"
    assert RUNTIME_SHARED_RESOURCES_PACKAGE.env_var == "GHOSTRIGGER_RUNTIME_SHARED_RESOURCES"
    assert RUNTIME_SHARED_RESOURCES_PACKAGE.version_export == "gr_runtime_shared_resources_version"
    assert (
        RUNTIME_SHARED_RESOURCES_PACKAGE.capabilities_export
        == "gr_runtime_shared_resources_capabilities_json"
    )


def test_renderer_contracts_package_spec_names_current_contract() -> None:
    assert RENDERER_CONTRACTS_PACKAGE.name == "GhostRigger.Core.Rendering.Contracts"
    assert RENDERER_CONTRACTS_PACKAGE.dll_name == "GhostRigger.Core.Rendering.Contracts.dll"
    assert RENDERER_CONTRACTS_PACKAGE.env_var == "GHOSTRIGGER_RENDERER_CONTRACTS"
    assert RENDERER_CONTRACTS_PACKAGE.version_export == "gr_renderer_contracts_version"
    assert RENDERER_CONTRACTS_PACKAGE.capabilities_export == "gr_renderer_contracts_capabilities_json"


def test_renderer_null_package_spec_names_current_contract() -> None:
    assert RENDERER_NULL_PACKAGE.name == "GhostRigger.Core.Rendering.Backends.Null"
    assert RENDERER_NULL_PACKAGE.dll_name == "GhostRigger.Core.Rendering.Backends.Null.dll"
    assert RENDERER_NULL_PACKAGE.env_var == "GHOSTRIGGER_RENDERER_NULL"
    assert RENDERER_NULL_PACKAGE.version_export == "gr_renderer_null_version"
    assert RENDERER_NULL_PACKAGE.capabilities_export == "gr_renderer_null_capabilities_json"


def test_renderer_d3d12_package_spec_names_current_contract() -> None:
    assert RENDERER_D3D12_PACKAGE.name == "GhostRigger.Core.Rendering.Backends.D3D12"
    assert RENDERER_D3D12_PACKAGE.dll_name == "GhostRigger.Core.Rendering.Backends.D3D12.dll"
    assert RENDERER_D3D12_PACKAGE.env_var == "GHOSTRIGGER_RENDERER_D3D12"
    assert RENDERER_D3D12_PACKAGE.version_export == "gr_renderer_d3d12_version"
    assert RENDERER_D3D12_PACKAGE.capabilities_export == "gr_renderer_d3d12_capabilities_json"


def test_renderer_moderngl_package_spec_names_current_contract() -> None:
    assert RENDERER_MODERNGL_PACKAGE.name == "GhostRigger.Core.Rendering.Backends.ModernGL"
    assert RENDERER_MODERNGL_PACKAGE.dll_name == "GhostRigger.Core.Rendering.Backends.ModernGL.dll"
    assert RENDERER_MODERNGL_PACKAGE.env_var == "GHOSTRIGGER_RENDERER_MODERNGL"
    assert RENDERER_MODERNGL_PACKAGE.version_export == "gr_renderer_moderngl_version"
    assert RENDERER_MODERNGL_PACKAGE.capabilities_export == "gr_renderer_moderngl_capabilities_json"


def test_renderer_pygfx_package_spec_names_current_contract() -> None:
    assert RENDERER_PYGFX_PACKAGE.name == "GhostRigger.Core.Rendering.Backends.PyGFX"
    assert RENDERER_PYGFX_PACKAGE.dll_name == "GhostRigger.Core.Rendering.Backends.PyGFX.dll"
    assert RENDERER_PYGFX_PACKAGE.env_var == "GHOSTRIGGER_RENDERER_PYGFX"
    assert RENDERER_PYGFX_PACKAGE.version_export == "gr_renderer_pygfx_version"
    assert RENDERER_PYGFX_PACKAGE.capabilities_export == "gr_renderer_pygfx_capabilities_json"


def test_tools_retargeting_package_spec_names_current_contract() -> None:
    assert TOOLS_RETARGETING_PACKAGE.name == "GhostRigger.Core.Tools.Retargeting"
    assert TOOLS_RETARGETING_PACKAGE.dll_name == "GhostRigger.Core.Tools.Retargeting.dll"
    assert TOOLS_RETARGETING_PACKAGE.env_var == "GHOSTRIGGER_TOOLS_RETARGETING"
    assert TOOLS_RETARGETING_PACKAGE.version_export == "gr_tools_retargeting_version"
    assert TOOLS_RETARGETING_PACKAGE.capabilities_export == "gr_tools_retargeting_capabilities_json"


def test_tools_export_package_spec_names_current_contract() -> None:
    assert TOOLS_EXPORT_PACKAGE.name == "GhostRigger.Core.Tools.Export"
    assert TOOLS_EXPORT_PACKAGE.dll_name == "GhostRigger.Core.Tools.Export.dll"
    assert TOOLS_EXPORT_PACKAGE.env_var == "GHOSTRIGGER_TOOLS_EXPORT"
    assert TOOLS_EXPORT_PACKAGE.version_export == "gr_tools_export_version"
    assert TOOLS_EXPORT_PACKAGE.capabilities_export == "gr_tools_export_capabilities_json"


def test_tools_character_builder_package_spec_names_current_contract() -> None:
    assert TOOLS_CHARACTER_BUILDER_PACKAGE.name == "GhostRigger.Core.Tools.CharacterBuilder"
    assert TOOLS_CHARACTER_BUILDER_PACKAGE.dll_name == "GhostRigger.Core.Tools.CharacterBuilder.dll"
    assert TOOLS_CHARACTER_BUILDER_PACKAGE.env_var == "GHOSTRIGGER_TOOLS_CHARACTER_BUILDER"
    assert TOOLS_CHARACTER_BUILDER_PACKAGE.version_export == "gr_tools_character_builder_version"
    assert (
        TOOLS_CHARACTER_BUILDER_PACKAGE.capabilities_export
        == "gr_tools_character_builder_capabilities_json"
    )


def test_browser_tool_package_specs_name_current_contracts() -> None:
    cases = (
        (
            TOOLS_CONTENT_BROWSER_PACKAGE,
            "GhostRigger.Core.Tools.ContentBrowser",
            "GHOSTRIGGER_TOOLS_CONTENT_BROWSER",
            "gr_tools_content_browser_version",
            "gr_tools_content_browser_capabilities_json",
        ),
        (
            TOOLS_RESOURCE_BROWSER_PACKAGE,
            "GhostRigger.Core.Tools.ResourceBrowser",
            "GHOSTRIGGER_TOOLS_RESOURCE_BROWSER",
            "gr_tools_resource_browser_version",
            "gr_tools_resource_browser_capabilities_json",
        ),
        (
            TOOLS_TWO_DA_BROWSER_PACKAGE,
            "GhostRigger.Core.Tools.TwoDABrowser",
            "GHOSTRIGGER_TOOLS_TWO_DA_BROWSER",
            "gr_tools_two_da_browser_version",
            "gr_tools_two_da_browser_capabilities_json",
        ),
    )

    for spec, name, env_var, version_export, capabilities_export in cases:
        assert spec.name == name
        assert spec.dll_name == f"{name}.dll"
        assert spec.env_var == env_var
        assert spec.version_export == version_export
        assert spec.capabilities_export == capabilities_export


def test_scene_workbench_tool_package_specs_name_current_contracts() -> None:
    cases = (
        (
            TOOLS_SCENE_INFORMATION_PACKAGE,
            "GhostRigger.Core.Tools.SceneInformation",
            "GHOSTRIGGER_TOOLS_SCENE_INFORMATION",
            "gr_tools_scene_information_version",
            "gr_tools_scene_information_capabilities_json",
        ),
        (
            TOOLS_PROPERTIES_PACKAGE,
            "GhostRigger.Core.Tools.Properties",
            "GHOSTRIGGER_TOOLS_PROPERTIES",
            "gr_tools_properties_version",
            "gr_tools_properties_capabilities_json",
        ),
        (
            TOOLS_LIGHTING_PACKAGE,
            "GhostRigger.Core.Tools.Lighting",
            "GHOSTRIGGER_TOOLS_LIGHTING",
            "gr_tools_lighting_version",
            "gr_tools_lighting_capabilities_json",
        ),
        (
            TOOLS_CAMERA_PACKAGE,
            "GhostRigger.Core.Tools.Camera",
            "GHOSTRIGGER_TOOLS_CAMERA",
            "gr_tools_camera_version",
            "gr_tools_camera_capabilities_json",
        ),
        (
            TOOLS_MODULE_MESHES_PACKAGE,
            "GhostRigger.Core.Tools.ModuleMeshes",
            "GHOSTRIGGER_TOOLS_MODULE_MESHES",
            "gr_tools_module_meshes_version",
            "gr_tools_module_meshes_capabilities_json",
        ),
    )

    for spec, name, env_var, version_export, capabilities_export in cases:
        assert spec.name == name
        assert spec.dll_name == f"{name}.dll"
        assert spec.env_var == env_var
        assert spec.version_export == version_export
        assert spec.capabilities_export == capabilities_export


def test_final_phase_one_tool_package_specs_name_current_contracts() -> None:
    cases = (
        (
            TOOLS_BODY_ATTACHMENT_SYSTEM_PACKAGE,
            "GhostRigger.Core.Tools.BAS",
            "GHOSTRIGGER_TOOLS_BODY_ATTACHMENT_SYSTEM",
            "gr_tools_body_attachment_system_version",
            "gr_tools_body_attachment_system_capabilities_json",
        ),
        (
            TOOLS_NODES_SKELETON_BROWSER_PACKAGE,
            "GhostRigger.Core.Tools.NodeSkeletonBrowser",
            "GHOSTRIGGER_TOOLS_NODES_SKELETON_BROWSER",
            "gr_tools_nodes_skeleton_browser_version",
            "gr_tools_nodes_skeleton_browser_capabilities_json",
        ),
        (
            TOOLS_SPRITE_MATERIALS_PACKAGE,
            "GhostRigger.Core.Tools.SpriteMaterials",
            "GHOSTRIGGER_TOOLS_SPRITE_MATERIALS",
            "gr_tools_sprite_materials_version",
            "gr_tools_sprite_materials_capabilities_json",
        ),
        (
            TOOLS_PIVOT_CONTROLS_PACKAGE,
            "GhostRigger.Core.Tools.PivotControls",
            "GHOSTRIGGER_TOOLS_PIVOT_CONTROLS",
            "gr_tools_pivot_controls_version",
            "gr_tools_pivot_controls_capabilities_json",
        ),
        (
            TOOLS_SEQUENCE_EDITOR_PACKAGE,
            "GhostRigger.Core.Tools.SequenceEditor",
            "GHOSTRIGGER_TOOLS_SEQUENCE_EDITOR",
            "gr_tools_sequence_editor_version",
            "gr_tools_sequence_editor_capabilities_json",
        ),
    )

    for spec, name, env_var, version_export, capabilities_export in cases:
        assert spec.name == name
        assert spec.dll_name == f"{name}.dll"
        assert spec.env_var == env_var
        assert spec.version_export == version_export
        assert spec.capabilities_export == capabilities_export


def test_windows_main_window_package_spec_names_current_contract() -> None:
    assert WINDOWS_MAIN_WINDOW_PACKAGE.name == "GhostRigger.Core.GUI.Display.Shell.Main"
    assert WINDOWS_MAIN_WINDOW_PACKAGE.dll_name == "GhostRigger.Core.GUI.Display.Shell.Main.dll"
    assert WINDOWS_MAIN_WINDOW_PACKAGE.env_var == "GHOSTRIGGER_WINDOWS_MAIN_WINDOW"
    assert WINDOWS_MAIN_WINDOW_PACKAGE.version_export == "gr_windows_main_window_version"
    assert (
        WINDOWS_MAIN_WINDOW_PACKAGE.capabilities_export
        == "gr_windows_main_window_capabilities_json"
    )


def test_extra_window_package_specs_name_current_contracts() -> None:
    cases = (
        (
            WINDOWS_LEVEL_EDITOR_PACKAGE,
            "GhostRigger.Core.Tools.ModuleEditor",
            "GHOSTRIGGER_WINDOWS_LEVEL_EDITOR",
            "gr_windows_level_editor_version",
            "gr_windows_level_editor_capabilities_json",
        ),
        (
            WINDOWS_ANIMATION_RETARGET_WORKBENCH_PACKAGE,
            "GhostRigger.Core.Tools.Retargeting.Workbench",
            "GHOSTRIGGER_WINDOWS_ANIMATION_RETARGET_WORKBENCH",
            "gr_windows_animation_retarget_workbench_version",
            "gr_windows_animation_retarget_workbench_capabilities_json",
        ),
        (
            WINDOWS_LEGACY_RIGGING_WINDOW_PACKAGE,
            "GhostRigger.Core.Tools.Rigging",
            "GHOSTRIGGER_WINDOWS_LEGACY_RIGGING_WINDOW",
            "gr_windows_legacy_rigging_window_version",
            "gr_windows_legacy_rigging_window_capabilities_json",
        ),
        (
            WINDOWS_UNREAL_ANIMATOR_WINDOW_PACKAGE,
            "GhostRigger.Core.Tools.UnrealAnimator",
            "GHOSTRIGGER_WINDOWS_UNREAL_ANIMATOR_WINDOW",
            "gr_windows_unreal_animator_window_version",
            "gr_windows_unreal_animator_window_capabilities_json",
        ),
    )

    for spec, name, env_var, version_export, capabilities_export in cases:
        assert spec.name == name
        assert spec.dll_name == f"{name}.dll"
        assert spec.env_var == env_var
        assert spec.version_export == version_export
        assert spec.capabilities_export == capabilities_export


def test_renderer_d3d12_guarded_metadata_capabilities_name_complete_phase_1_surface() -> None:
    assert RENDERER_D3D12_GUARDED_METADATA_CAPABILITIES == (
        "descriptor_allocator_readiness",
        "command_list_readiness",
        "surface_swap_chain_readiness",
        "render_target_metadata",
        "barrier_clear_pass_metadata",
        "command_recording_dry_run_frame",
        "guarded_command_recording_diagnostics",
        "no_draw_execution_fence_diagnostics",
        "present_readiness_metadata",
        "guarded_swap_chain_creation_diagnostics",
        "guarded_back_buffer_rtv_diagnostics",
        "guarded_barrier_clear_recording_diagnostics",
        "guarded_clear_pass_execution_fence_diagnostics",
        "post_clear_present_readiness_diagnostics",
        "guarded_present_call_diagnostics",
        "post_present_frame_accounting_diagnostics",
        "draw_list_readiness_metadata",
        "resource_binding_readiness_metadata",
        "pipeline_state_readiness_metadata",
        "guarded_shader_bytecode_metadata",
        "shader_reflection_input_layout_metadata",
        "guarded_root_signature_metadata",
        "guarded_pipeline_state_object_metadata",
        "guarded_draw_command_recording_metadata",
        "guarded_draw_submission_readiness_metadata",
        "guarded_post_draw_frame_accounting_readiness_metadata",
    )


def test_renderer_d3d12_status_reports_guarded_metadata_capabilities(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dll_path = tmp_path / "GhostRigger.Core.Rendering.Backends.D3D12.dll"
    dll_path.write_bytes(b"fake")

    monkeypatch.setattr(package_registry.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        package_registry,
        "_load_library",
        lambda path: _FakeRendererD3D12Dll(),
    )

    status = query_renderer_d3d12_status([tmp_path])

    assert status.available is True
    assert status.version == "0.1.0"
    assert status.capabilities is not None
    assert status.capabilities["draw_submission_enabled"] is False
    assert (
        renderer_d3d12_guarded_metadata_capabilities(status)
        == RENDERER_D3D12_GUARDED_METADATA_CAPABILITIES
    )


def test_renderer_moderngl_status_reports_diagnostic_capabilities(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dll_path = tmp_path / "GhostRigger.Core.Rendering.Backends.ModernGL.dll"
    dll_path.write_bytes(b"fake")

    monkeypatch.setattr(package_registry.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        package_registry,
        "_load_library",
        lambda path: _FakeRendererModernGLDll(),
    )

    status = query_renderer_moderngl_status([tmp_path])

    assert status.available is True
    assert status.version == "0.1.0"
    assert status.capabilities is not None
    assert status.capabilities["renderer_backend"] is True
    assert status.capabilities["backend"] == "moderngl"
    assert status.capabilities["python_adapter_required"] is True
    assert status.capabilities["native_device_owner"] is False
    assert status.capabilities["draw_submission_enabled"] is False


def test_renderer_pygfx_status_reports_diagnostic_capabilities(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dll_path = tmp_path / "GhostRigger.Core.Rendering.Backends.PyGFX.dll"
    dll_path.write_bytes(b"fake")

    monkeypatch.setattr(package_registry.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        package_registry,
        "_load_library",
        lambda path: _FakeRendererPyGFXDll(),
    )

    status = query_renderer_pygfx_status([tmp_path])

    assert status.available is True
    assert status.version == "0.1.0"
    assert status.capabilities is not None
    assert status.capabilities["renderer_backend"] is True
    assert status.capabilities["backend"] == "pygfx"
    assert status.capabilities["python_adapter_required"] is True
    assert status.capabilities["native_device_owner"] is False
    assert status.capabilities["draw_submission_enabled"] is False


def test_tools_retargeting_status_reports_diagnostic_capabilities(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dll_path = tmp_path / "GhostRigger.Core.Tools.Retargeting.dll"
    dll_path.write_bytes(b"fake")

    monkeypatch.setattr(package_registry.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        package_registry,
        "_load_library",
        lambda path: _FakeToolsRetargetingDll(),
    )

    status = query_tools_retargeting_status([tmp_path])

    assert status.available is True
    assert status.version == "0.1.0"
    assert status.capabilities is not None
    assert status.capabilities["tool_package"] is True
    assert status.capabilities["owner_surface"] == "Retarget Workbench"
    assert status.capabilities["native_solve_enabled"] is False
    assert status.capabilities["python_fallback_required"] is True


def test_tools_export_status_reports_diagnostic_capabilities(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dll_path = tmp_path / "GhostRigger.Core.Tools.Export.dll"
    dll_path.write_bytes(b"fake")

    monkeypatch.setattr(package_registry.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        package_registry,
        "_load_library",
        lambda path: _FakeToolsExportDll(),
    )

    status = query_tools_export_status([tmp_path])

    assert status.available is True
    assert status.version == "0.1.0"
    assert status.capabilities is not None
    assert status.capabilities["tool_package"] is True
    assert status.capabilities["owner_surface"] == "Export and validation workflow"
    assert status.capabilities["native_write_enabled"] is False
    assert status.capabilities["python_fallback_required"] is True


def test_tools_character_builder_status_reports_diagnostic_capabilities(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dll_path = tmp_path / "GhostRigger.Core.Tools.CharacterBuilder.dll"
    dll_path.write_bytes(b"fake")

    monkeypatch.setattr(package_registry.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        package_registry,
        "_load_library",
        lambda path: _FakeToolsCharacterBuilderDll(),
    )

    status = query_tools_character_builder_status([tmp_path])

    assert status.available is True
    assert status.version == "0.1.0"
    assert status.capabilities is not None
    assert status.capabilities["tool_package"] is True
    assert status.capabilities["owner_surface"] == "Character Studio"
    assert status.capabilities["native_autofit_enabled"] is False
    assert status.capabilities["python_fallback_required"] is True


def test_windows_main_window_status_reports_diagnostic_capabilities(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dll_path = tmp_path / "GhostRigger.Core.GUI.Display.Shell.Main.dll"
    dll_path.write_bytes(b"fake")

    monkeypatch.setattr(package_registry.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        package_registry,
        "_load_library",
        lambda path: _FakeWindowsMainWindowDll(),
    )

    status = query_windows_main_window_status([tmp_path])

    assert status.available is True
    assert status.version == "0.1.0"
    assert status.capabilities is not None
    assert status.capabilities["window_package"] is True
    assert status.capabilities["owner_surface"] == "Main window composition shell"
    assert status.capabilities["native_shell_enabled"] is False
    assert status.capabilities["python_fallback_required"] is True
