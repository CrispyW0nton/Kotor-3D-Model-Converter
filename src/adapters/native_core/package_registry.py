"""Thin native package availability checks for Phase 1 C++ integration."""

from __future__ import annotations

import ctypes
import json
import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_NATIVE_CORE_DLL = "GhostRigger.Native.NativeCore.dll"


@dataclass(frozen=True)
class NativePackageStatus:
    name: str
    available: bool
    version: str = ""
    capabilities: dict[str, object] | None = None
    path: str = ""
    reason: str = ""


@dataclass(frozen=True)
class NativePackageSpec:
    name: str
    dll_name: str
    env_var: str = ""
    version_export: str = ""
    capabilities_export: str = ""
    windows_only: bool = True


NATIVE_CORE_PACKAGE = NativePackageSpec(
    name="GhostRigger.Native.NativeCore",
    dll_name=_NATIVE_CORE_DLL,
    env_var="GHOSTRIGGER_NATIVE_CORE",
    version_export="gr_native_core_version",
    capabilities_export="gr_native_core_capabilities_json",
)

RUNTIME_SHARED_CONTRACTS_PACKAGE = NativePackageSpec(
    name="GhostRigger.Runtime.Shared.Contracts",
    dll_name="GhostRigger.Runtime.Shared.Contracts.dll",
    env_var="GHOSTRIGGER_RUNTIME_SHARED_CONTRACTS",
    version_export="gr_runtime_shared_contracts_version",
    capabilities_export="gr_runtime_shared_contracts_capabilities_json",
)

RUNTIME_SHARED_DESCRIPTORS_PACKAGE = NativePackageSpec(
    name="GhostRigger.Runtime.Shared.Descriptors",
    dll_name="GhostRigger.Runtime.Shared.Descriptors.dll",
    env_var="GHOSTRIGGER_RUNTIME_SHARED_DESCRIPTORS",
    version_export="gr_runtime_shared_descriptors_version",
    capabilities_export="gr_runtime_shared_descriptors_capabilities_json",
)

RUNTIME_SHARED_RESOURCES_PACKAGE = NativePackageSpec(
    name="GhostRigger.Runtime.Shared.Resources",
    dll_name="GhostRigger.Runtime.Shared.Resources.dll",
    env_var="GHOSTRIGGER_RUNTIME_SHARED_RESOURCES",
    version_export="gr_runtime_shared_resources_version",
    capabilities_export="gr_runtime_shared_resources_capabilities_json",
)

RENDERER_CONTRACTS_PACKAGE = NativePackageSpec(
    name="GhostRigger.Renderer.Contracts",
    dll_name="GhostRigger.Renderer.Contracts.dll",
    env_var="GHOSTRIGGER_RENDERER_CONTRACTS",
    version_export="gr_renderer_contracts_version",
    capabilities_export="gr_renderer_contracts_capabilities_json",
)

RENDERER_NULL_PACKAGE = NativePackageSpec(
    name="GhostRigger.Renderer.Null",
    dll_name="GhostRigger.Renderer.Null.dll",
    env_var="GHOSTRIGGER_RENDERER_NULL",
    version_export="gr_renderer_null_version",
    capabilities_export="gr_renderer_null_capabilities_json",
)

RENDERER_D3D12_PACKAGE = NativePackageSpec(
    name="GhostRigger.Renderer.D3D12",
    dll_name="GhostRigger.Renderer.D3D12.dll",
    env_var="GHOSTRIGGER_RENDERER_D3D12",
    version_export="gr_renderer_d3d12_version",
    capabilities_export="gr_renderer_d3d12_capabilities_json",
)

RENDERER_MODERNGL_PACKAGE = NativePackageSpec(
    name="GhostRigger.Renderer.ModernGL",
    dll_name="GhostRigger.Renderer.ModernGL.dll",
    env_var="GHOSTRIGGER_RENDERER_MODERNGL",
    version_export="gr_renderer_moderngl_version",
    capabilities_export="gr_renderer_moderngl_capabilities_json",
)

RENDERER_PYGFX_PACKAGE = NativePackageSpec(
    name="GhostRigger.Renderer.PyGFX",
    dll_name="GhostRigger.Renderer.PyGFX.dll",
    env_var="GHOSTRIGGER_RENDERER_PYGFX",
    version_export="gr_renderer_pygfx_version",
    capabilities_export="gr_renderer_pygfx_capabilities_json",
)

TOOLS_RETARGETING_PACKAGE = NativePackageSpec(
    name="GhostRigger.Tools.Retargeting",
    dll_name="GhostRigger.Tools.Retargeting.dll",
    env_var="GHOSTRIGGER_TOOLS_RETARGETING",
    version_export="gr_tools_retargeting_version",
    capabilities_export="gr_tools_retargeting_capabilities_json",
)

TOOLS_EXPORT_PACKAGE = NativePackageSpec(
    name="GhostRigger.Tools.Export",
    dll_name="GhostRigger.Tools.Export.dll",
    env_var="GHOSTRIGGER_TOOLS_EXPORT",
    version_export="gr_tools_export_version",
    capabilities_export="gr_tools_export_capabilities_json",
)

TOOLS_CHARACTER_BUILDER_PACKAGE = NativePackageSpec(
    name="GhostRigger.Tools.CharacterBuilder",
    dll_name="GhostRigger.Tools.CharacterBuilder.dll",
    env_var="GHOSTRIGGER_TOOLS_CHARACTER_BUILDER",
    version_export="gr_tools_character_builder_version",
    capabilities_export="gr_tools_character_builder_capabilities_json",
)

TOOLS_CONTENT_BROWSER_PACKAGE = NativePackageSpec(
    name="GhostRigger.Tools.ContentBrowser",
    dll_name="GhostRigger.Tools.ContentBrowser.dll",
    env_var="GHOSTRIGGER_TOOLS_CONTENT_BROWSER",
    version_export="gr_tools_content_browser_version",
    capabilities_export="gr_tools_content_browser_capabilities_json",
)

TOOLS_RESOURCE_BROWSER_PACKAGE = NativePackageSpec(
    name="GhostRigger.Tools.ResourceBrowser",
    dll_name="GhostRigger.Tools.ResourceBrowser.dll",
    env_var="GHOSTRIGGER_TOOLS_RESOURCE_BROWSER",
    version_export="gr_tools_resource_browser_version",
    capabilities_export="gr_tools_resource_browser_capabilities_json",
)

TOOLS_TWO_DA_BROWSER_PACKAGE = NativePackageSpec(
    name="GhostRigger.Tools.TwoDABrowser",
    dll_name="GhostRigger.Tools.TwoDABrowser.dll",
    env_var="GHOSTRIGGER_TOOLS_TWO_DA_BROWSER",
    version_export="gr_tools_two_da_browser_version",
    capabilities_export="gr_tools_two_da_browser_capabilities_json",
)

TOOLS_SCENE_INFORMATION_PACKAGE = NativePackageSpec(
    name="GhostRigger.Tools.SceneInformation",
    dll_name="GhostRigger.Tools.SceneInformation.dll",
    env_var="GHOSTRIGGER_TOOLS_SCENE_INFORMATION",
    version_export="gr_tools_scene_information_version",
    capabilities_export="gr_tools_scene_information_capabilities_json",
)

TOOLS_PROPERTIES_PACKAGE = NativePackageSpec(
    name="GhostRigger.Tools.Properties",
    dll_name="GhostRigger.Tools.Properties.dll",
    env_var="GHOSTRIGGER_TOOLS_PROPERTIES",
    version_export="gr_tools_properties_version",
    capabilities_export="gr_tools_properties_capabilities_json",
)

TOOLS_LIGHTING_PACKAGE = NativePackageSpec(
    name="GhostRigger.Tools.Lighting",
    dll_name="GhostRigger.Tools.Lighting.dll",
    env_var="GHOSTRIGGER_TOOLS_LIGHTING",
    version_export="gr_tools_lighting_version",
    capabilities_export="gr_tools_lighting_capabilities_json",
)

TOOLS_CAMERA_PACKAGE = NativePackageSpec(
    name="GhostRigger.Tools.Camera",
    dll_name="GhostRigger.Tools.Camera.dll",
    env_var="GHOSTRIGGER_TOOLS_CAMERA",
    version_export="gr_tools_camera_version",
    capabilities_export="gr_tools_camera_capabilities_json",
)

TOOLS_MODULE_MESHES_PACKAGE = NativePackageSpec(
    name="GhostRigger.Tools.ModuleMeshes",
    dll_name="GhostRigger.Tools.ModuleMeshes.dll",
    env_var="GHOSTRIGGER_TOOLS_MODULE_MESHES",
    version_export="gr_tools_module_meshes_version",
    capabilities_export="gr_tools_module_meshes_capabilities_json",
)

TOOLS_BODY_ATTACHMENT_SYSTEM_PACKAGE = NativePackageSpec(
    name="GhostRigger.Tools.BodyAttachmentSystem",
    dll_name="GhostRigger.Tools.BodyAttachmentSystem.dll",
    env_var="GHOSTRIGGER_TOOLS_BODY_ATTACHMENT_SYSTEM",
    version_export="gr_tools_body_attachment_system_version",
    capabilities_export="gr_tools_body_attachment_system_capabilities_json",
)

TOOLS_NODES_SKELETON_BROWSER_PACKAGE = NativePackageSpec(
    name="GhostRigger.Tools.NodesSkeletonBrowser",
    dll_name="GhostRigger.Tools.NodesSkeletonBrowser.dll",
    env_var="GHOSTRIGGER_TOOLS_NODES_SKELETON_BROWSER",
    version_export="gr_tools_nodes_skeleton_browser_version",
    capabilities_export="gr_tools_nodes_skeleton_browser_capabilities_json",
)

TOOLS_SPRITE_MATERIALS_PACKAGE = NativePackageSpec(
    name="GhostRigger.Tools.SpriteMaterials",
    dll_name="GhostRigger.Tools.SpriteMaterials.dll",
    env_var="GHOSTRIGGER_TOOLS_SPRITE_MATERIALS",
    version_export="gr_tools_sprite_materials_version",
    capabilities_export="gr_tools_sprite_materials_capabilities_json",
)

TOOLS_PIVOT_CONTROLS_PACKAGE = NativePackageSpec(
    name="GhostRigger.Tools.PivotControls",
    dll_name="GhostRigger.Tools.PivotControls.dll",
    env_var="GHOSTRIGGER_TOOLS_PIVOT_CONTROLS",
    version_export="gr_tools_pivot_controls_version",
    capabilities_export="gr_tools_pivot_controls_capabilities_json",
)

TOOLS_SEQUENCE_EDITOR_PACKAGE = NativePackageSpec(
    name="GhostRigger.Tools.SequenceEditor",
    dll_name="GhostRigger.Tools.SequenceEditor.dll",
    env_var="GHOSTRIGGER_TOOLS_SEQUENCE_EDITOR",
    version_export="gr_tools_sequence_editor_version",
    capabilities_export="gr_tools_sequence_editor_capabilities_json",
)

WINDOWS_MAIN_WINDOW_PACKAGE = NativePackageSpec(
    name="GhostRigger.Windows.MainWindow",
    dll_name="GhostRigger.Windows.MainWindow.dll",
    env_var="GHOSTRIGGER_WINDOWS_MAIN_WINDOW",
    version_export="gr_windows_main_window_version",
    capabilities_export="gr_windows_main_window_capabilities_json",
)

RENDERER_D3D12_GUARDED_METADATA_CAPABILITIES = (
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

NATIVE_CORE_DIAGNOSTICS_PACKAGE = NativePackageSpec(
    name="GhostRigger.Native.NativeCore.Diagnostics",
    dll_name="GhostRigger.Native.NativeCore.Diagnostics.dll",
    env_var="GHOSTRIGGER_NATIVE_CORE_DIAGNOSTICS",
    version_export="gr_native_core_diagnostics_version",
    capabilities_export="gr_native_core_diagnostics_capabilities_json",
)

NATIVE_CORE_MATH_PACKAGE = NativePackageSpec(
    name="GhostRigger.Native.NativeCore.Math",
    dll_name="GhostRigger.Native.NativeCore.Math.dll",
    env_var="GHOSTRIGGER_NATIVE_CORE_MATH",
    version_export="gr_native_core_math_version",
    capabilities_export="gr_native_core_math_capabilities_json",
)


def _candidate_output_dirs(repo_root: Path) -> Iterable[Path]:
    yield repo_root / "build" / "vs" / "x64" / "Debug"
    yield repo_root / "build" / "vs" / "x64" / "Release"
    yield repo_root / "build" / "vs" / "Win32" / "Debug"
    yield repo_root / "build" / "vs" / "Win32" / "Release"


def _candidate_paths(
    spec: NativePackageSpec,
    search_paths: Iterable[Path] | None = None,
) -> list[Path]:
    if search_paths is not None:
        return [Path(path) / spec.dll_name if Path(path).is_dir() else Path(path) for path in search_paths]

    override = os.environ.get(spec.env_var) if spec.env_var else ""
    if override:
        return [Path(override)]

    repo_root = Path(__file__).resolve().parents[3]
    return [directory / spec.dll_name for directory in _candidate_output_dirs(repo_root)]


def _load_library(path: Path) -> ctypes.CDLL:
    return ctypes.CDLL(str(path))


def query_native_package_status(
    spec: NativePackageSpec,
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    if spec.windows_only and platform.system() != "Windows":
        return NativePackageStatus(
            name=spec.name,
            available=False,
            reason=f"{spec.name} is currently a Windows native package.",
        )

    candidates = _candidate_paths(spec, search_paths)
    existing = [path for path in candidates if path.exists()]
    if not existing:
        return NativePackageStatus(
            name=spec.name,
            available=False,
            reason=f"{spec.dll_name} was not found.",
        )

    path = existing[0]
    try:
        dll = _load_library(path)
        version = ""
        capabilities: dict[str, object] | None = None
        if spec.version_export:
            version_func = getattr(dll, spec.version_export)
            version_func.restype = ctypes.c_char_p
            version = (version_func() or b"").decode("utf-8", errors="replace")
        if spec.capabilities_export:
            capabilities_func = getattr(dll, spec.capabilities_export)
            capabilities_func.restype = ctypes.c_char_p
            raw_capabilities = (capabilities_func() or b"{}").decode(
                "utf-8",
                errors="replace",
            )
            capabilities = json.loads(raw_capabilities)
    except Exception as exc:
        return NativePackageStatus(
            name=spec.name,
            available=False,
            path=str(path),
            reason=str(exc),
        )

    return NativePackageStatus(
        name=spec.name,
        available=True,
        version=version,
        capabilities=capabilities,
        path=str(path),
    )


def query_native_core_status(search_paths: Iterable[Path] | None = None) -> NativePackageStatus:
    return query_native_package_status(NATIVE_CORE_PACKAGE, search_paths)


def query_native_core_diagnostics_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(NATIVE_CORE_DIAGNOSTICS_PACKAGE, search_paths)


def query_native_core_math_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(NATIVE_CORE_MATH_PACKAGE, search_paths)


def query_runtime_shared_contracts_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(RUNTIME_SHARED_CONTRACTS_PACKAGE, search_paths)


def query_runtime_shared_descriptors_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(RUNTIME_SHARED_DESCRIPTORS_PACKAGE, search_paths)


def query_runtime_shared_resources_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(RUNTIME_SHARED_RESOURCES_PACKAGE, search_paths)


def query_renderer_contracts_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(RENDERER_CONTRACTS_PACKAGE, search_paths)


def query_renderer_null_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(RENDERER_NULL_PACKAGE, search_paths)


def query_renderer_d3d12_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(RENDERER_D3D12_PACKAGE, search_paths)


def query_renderer_moderngl_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(RENDERER_MODERNGL_PACKAGE, search_paths)


def query_renderer_pygfx_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(RENDERER_PYGFX_PACKAGE, search_paths)


def query_tools_retargeting_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(TOOLS_RETARGETING_PACKAGE, search_paths)


def query_tools_export_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(TOOLS_EXPORT_PACKAGE, search_paths)


def query_tools_character_builder_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(TOOLS_CHARACTER_BUILDER_PACKAGE, search_paths)


def query_tools_content_browser_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(TOOLS_CONTENT_BROWSER_PACKAGE, search_paths)


def query_tools_resource_browser_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(TOOLS_RESOURCE_BROWSER_PACKAGE, search_paths)


def query_tools_two_da_browser_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(TOOLS_TWO_DA_BROWSER_PACKAGE, search_paths)


def query_tools_scene_information_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(TOOLS_SCENE_INFORMATION_PACKAGE, search_paths)


def query_tools_properties_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(TOOLS_PROPERTIES_PACKAGE, search_paths)


def query_tools_lighting_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(TOOLS_LIGHTING_PACKAGE, search_paths)


def query_tools_camera_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(TOOLS_CAMERA_PACKAGE, search_paths)


def query_tools_module_meshes_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(TOOLS_MODULE_MESHES_PACKAGE, search_paths)


def query_tools_body_attachment_system_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(TOOLS_BODY_ATTACHMENT_SYSTEM_PACKAGE, search_paths)


def query_tools_nodes_skeleton_browser_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(TOOLS_NODES_SKELETON_BROWSER_PACKAGE, search_paths)


def query_tools_sprite_materials_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(TOOLS_SPRITE_MATERIALS_PACKAGE, search_paths)


def query_tools_pivot_controls_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(TOOLS_PIVOT_CONTROLS_PACKAGE, search_paths)


def query_tools_sequence_editor_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(TOOLS_SEQUENCE_EDITOR_PACKAGE, search_paths)


def query_windows_main_window_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(WINDOWS_MAIN_WINDOW_PACKAGE, search_paths)


def renderer_d3d12_guarded_metadata_capabilities(
    status: NativePackageStatus,
) -> tuple[str, ...]:
    capabilities = status.capabilities or {}
    raw_names = capabilities.get("guarded_metadata_capabilities", ())
    if not isinstance(raw_names, list):
        return ()
    names = tuple(name for name in raw_names if isinstance(name, str))
    return tuple(
        name for name in RENDERER_D3D12_GUARDED_METADATA_CAPABILITIES if name in names
    )
