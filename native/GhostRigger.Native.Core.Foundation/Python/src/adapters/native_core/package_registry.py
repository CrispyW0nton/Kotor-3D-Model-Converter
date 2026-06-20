"""Thin native package availability checks for Phase 1 C++ integration."""

from __future__ import annotations

import ctypes
import json
import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_NATIVE_CORE_DLL = "GhostRigger.Native.Core.Foundation.dll"
_CORE_DLL_PREFIX = "GhostRigger.Core."
_CORE_GUI_DLL_PREFIX = "GhostRigger.Core.GUI."
_CORE_TOOLS_DLL_PREFIX = "GhostRigger.Core.Tools."
_DLL_SUFFIX = ".dll"


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
    fallback_dll_names: tuple[str, ...] = ()
    env_var: str = ""
    version_export: str = ""
    capabilities_export: str = ""
    windows_only: bool = True


NATIVE_CORE_PACKAGE = NativePackageSpec(
    name="GhostRigger.Native.Core.Foundation",
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
    name="GhostRigger.Core.Rendering.Contracts",
    dll_name="GhostRigger.Core.Rendering.Contracts.dll",
    env_var="GHOSTRIGGER_RENDERER_CONTRACTS",
    version_export="gr_renderer_contracts_version",
    capabilities_export="gr_renderer_contracts_capabilities_json",
)

RENDERER_NULL_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Rendering.Backends.Null",
    dll_name="GhostRigger.Core.Rendering.Backends.Null.dll",
    env_var="GHOSTRIGGER_RENDERER_NULL",
    version_export="gr_renderer_null_version",
    capabilities_export="gr_renderer_null_capabilities_json",
)

RENDERER_D3D12_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Rendering.Backends.D3D12",
    dll_name="GhostRigger.Core.Rendering.Backends.D3D12.dll",
    env_var="GHOSTRIGGER_RENDERER_D3D12",
    version_export="gr_renderer_d3d12_version",
    capabilities_export="gr_renderer_d3d12_capabilities_json",
)

RENDERER_MODERNGL_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Rendering.Backends.ModernGL",
    dll_name="GhostRigger.Core.Rendering.Backends.ModernGL.dll",
    env_var="GHOSTRIGGER_RENDERER_MODERNGL",
    version_export="gr_renderer_moderngl_version",
    capabilities_export="gr_renderer_moderngl_capabilities_json",
)

RENDERER_PYGFX_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Rendering.Backends.PyGFX",
    dll_name="GhostRigger.Core.Rendering.Backends.PyGFX.dll",
    env_var="GHOSTRIGGER_RENDERER_PYGFX",
    version_export="gr_renderer_pygfx_version",
    capabilities_export="gr_renderer_pygfx_capabilities_json",
)

TOOLS_RETARGETING_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Tools.Retargeting",
    dll_name="GhostRigger.Core.Tools.Retargeting.dll",
    env_var="GHOSTRIGGER_TOOLS_RETARGETING",
    version_export="gr_tools_retargeting_version",
    capabilities_export="gr_tools_retargeting_capabilities_json",
)

TOOLS_EXPORT_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Tools.Export",
    dll_name="GhostRigger.Core.Tools.Export.dll",
    env_var="GHOSTRIGGER_TOOLS_EXPORT",
    version_export="gr_tools_export_version",
    capabilities_export="gr_tools_export_capabilities_json",
)

TOOLS_CHARACTER_BUILDER_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Tools.CharacterBuilder",
    dll_name="GhostRigger.Core.Tools.CharacterBuilder.dll",
    env_var="GHOSTRIGGER_TOOLS_CHARACTER_BUILDER",
    version_export="gr_tools_character_builder_version",
    capabilities_export="gr_tools_character_builder_capabilities_json",
)

TOOLS_CONTENT_BROWSER_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Tools.ContentBrowser",
    dll_name="GhostRigger.Core.Tools.ContentBrowser.dll",
    env_var="GHOSTRIGGER_TOOLS_CONTENT_BROWSER",
    version_export="gr_tools_content_browser_version",
    capabilities_export="gr_tools_content_browser_capabilities_json",
)

TOOLS_RESOURCE_BROWSER_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Tools.ResourceBrowser",
    dll_name="GhostRigger.Core.Tools.ResourceBrowser.dll",
    env_var="GHOSTRIGGER_TOOLS_RESOURCE_BROWSER",
    version_export="gr_tools_resource_browser_version",
    capabilities_export="gr_tools_resource_browser_capabilities_json",
)

TOOLS_TWO_DA_BROWSER_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Tools.TwoDABrowser",
    dll_name="GhostRigger.Core.Tools.TwoDABrowser.dll",
    env_var="GHOSTRIGGER_TOOLS_TWO_DA_BROWSER",
    version_export="gr_tools_two_da_browser_version",
    capabilities_export="gr_tools_two_da_browser_capabilities_json",
)

TOOLS_SCENE_INFORMATION_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Tools.SceneInformation",
    dll_name="GhostRigger.Core.Tools.SceneInformation.dll",
    env_var="GHOSTRIGGER_TOOLS_SCENE_INFORMATION",
    version_export="gr_tools_scene_information_version",
    capabilities_export="gr_tools_scene_information_capabilities_json",
)

TOOLS_PROPERTIES_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Tools.Properties",
    dll_name="GhostRigger.Core.Tools.Properties.dll",
    env_var="GHOSTRIGGER_TOOLS_PROPERTIES",
    version_export="gr_tools_properties_version",
    capabilities_export="gr_tools_properties_capabilities_json",
)

TOOLS_LIGHTING_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Tools.Lighting",
    dll_name="GhostRigger.Core.Tools.Lighting.dll",
    env_var="GHOSTRIGGER_TOOLS_LIGHTING",
    version_export="gr_tools_lighting_version",
    capabilities_export="gr_tools_lighting_capabilities_json",
)

TOOLS_CAMERA_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Tools.Camera",
    dll_name="GhostRigger.Core.Tools.Camera.dll",
    env_var="GHOSTRIGGER_TOOLS_CAMERA",
    version_export="gr_tools_camera_version",
    capabilities_export="gr_tools_camera_capabilities_json",
)

TOOLS_MODULE_MESHES_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Tools.ModuleMeshes",
    dll_name="GhostRigger.Core.Tools.ModuleMeshes.dll",
    env_var="GHOSTRIGGER_TOOLS_MODULE_MESHES",
    version_export="gr_tools_module_meshes_version",
    capabilities_export="gr_tools_module_meshes_capabilities_json",
)

TOOLS_BODY_ATTACHMENT_SYSTEM_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Tools.BAS",
    dll_name="GhostRigger.Core.Tools.BAS.dll",
    env_var="GHOSTRIGGER_TOOLS_BODY_ATTACHMENT_SYSTEM",
    version_export="gr_tools_body_attachment_system_version",
    capabilities_export="gr_tools_body_attachment_system_capabilities_json",
)

TOOLS_NODES_SKELETON_BROWSER_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Tools.NodeSkeletonBrowser",
    dll_name="GhostRigger.Core.Tools.NodeSkeletonBrowser.dll",
    env_var="GHOSTRIGGER_TOOLS_NODES_SKELETON_BROWSER",
    version_export="gr_tools_nodes_skeleton_browser_version",
    capabilities_export="gr_tools_nodes_skeleton_browser_capabilities_json",
)

TOOLS_SPRITE_MATERIALS_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Tools.SpriteMaterials",
    dll_name="GhostRigger.Core.Tools.SpriteMaterials.dll",
    env_var="GHOSTRIGGER_TOOLS_SPRITE_MATERIALS",
    version_export="gr_tools_sprite_materials_version",
    capabilities_export="gr_tools_sprite_materials_capabilities_json",
)

TOOLS_PIVOT_CONTROLS_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Tools.PivotControls",
    dll_name="GhostRigger.Core.Tools.PivotControls.dll",
    env_var="GHOSTRIGGER_TOOLS_PIVOT_CONTROLS",
    version_export="gr_tools_pivot_controls_version",
    capabilities_export="gr_tools_pivot_controls_capabilities_json",
)

TOOLS_SEQUENCE_EDITOR_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Tools.SequenceEditor",
    dll_name="GhostRigger.Core.Tools.SequenceEditor.dll",
    env_var="GHOSTRIGGER_TOOLS_SEQUENCE_EDITOR",
    version_export="gr_tools_sequence_editor_version",
    capabilities_export="gr_tools_sequence_editor_capabilities_json",
)

WINDOWS_MAIN_WINDOW_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.GUI.Display.Shell.Main",
    dll_name="GhostRigger.Core.GUI.Display.Shell.Main.dll",
    env_var="GHOSTRIGGER_WINDOWS_MAIN_WINDOW",
    version_export="gr_windows_main_window_version",
    capabilities_export="gr_windows_main_window_capabilities_json",
)

WINDOWS_LEVEL_EDITOR_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Tools.ModuleEditor",
    dll_name="GhostRigger.Core.Tools.ModuleEditor.dll",
    env_var="GHOSTRIGGER_WINDOWS_LEVEL_EDITOR",
    version_export="gr_windows_level_editor_version",
    capabilities_export="gr_windows_level_editor_capabilities_json",
)

WINDOWS_ANIMATION_RETARGET_WORKBENCH_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Tools.Retargeting.Workbench",
    dll_name="GhostRigger.Core.Tools.Retargeting.Workbench.dll",
    env_var="GHOSTRIGGER_WINDOWS_ANIMATION_RETARGET_WORKBENCH",
    version_export="gr_windows_animation_retarget_workbench_version",
    capabilities_export="gr_windows_animation_retarget_workbench_capabilities_json",
)

WINDOWS_LEGACY_RIGGING_WINDOW_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Tools.Rigging",
    dll_name="GhostRigger.Core.Tools.Rigging.dll",
    env_var="GHOSTRIGGER_WINDOWS_LEGACY_RIGGING_WINDOW",
    version_export="gr_windows_legacy_rigging_window_version",
    capabilities_export="gr_windows_legacy_rigging_window_capabilities_json",
)

WINDOWS_UNREAL_ANIMATOR_WINDOW_PACKAGE = NativePackageSpec(
    name="GhostRigger.Core.Tools.UnrealAnimator",
    dll_name="GhostRigger.Core.Tools.UnrealAnimator.dll",
    env_var="GHOSTRIGGER_WINDOWS_UNREAL_ANIMATOR_WINDOW",
    version_export="gr_windows_unreal_animator_window_version",
    capabilities_export="gr_windows_unreal_animator_window_capabilities_json",
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
    name="GhostRigger.Native.Core.Diagnostics",
    dll_name="GhostRigger.Native.Core.Diagnostics.dll",
    env_var="GHOSTRIGGER_NATIVE_CORE_DIAGNOSTICS",
    version_export="gr_native_core_diagnostics_version",
    capabilities_export="gr_native_core_diagnostics_capabilities_json",
)

NATIVE_CORE_MATH_PACKAGE = NativePackageSpec(
    name="GhostRigger.Native.Core.Math",
    dll_name="GhostRigger.Native.Core.Math.dll",
    env_var="GHOSTRIGGER_NATIVE_CORE_MATH",
    version_export="gr_native_core_math_version",
    capabilities_export="gr_native_core_math_capabilities_json",
)


def _dll_names_for_spec(spec: NativePackageSpec) -> tuple[str, ...]:
    names: list[str] = []
    for dll_name in (
        spec.dll_name,
    ):
        if dll_name not in names:
            names.append(dll_name)
    return tuple(names)


PYTHON_MODULE_PACKAGE_SPECS = (
    NativePackageSpec(
        name="GhostRigger.Core.Scene.Modules",
        dll_name="GhostRigger.Core.Scene.Modules.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_SCENE_MODULES",
        version_export="gr_modules_version",
        capabilities_export="gr_modules_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Scene.Level",
        dll_name="GhostRigger.Core.Scene.Level.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_SCENE_LEVEL",
        version_export="gr_level_version",
        capabilities_export="gr_level_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Scene",
        dll_name="GhostRigger.Core.Scene.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_SCENE",
        version_export="gr_scene_version",
        capabilities_export="gr_scene_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Workflow.Animation",
        dll_name="GhostRigger.Core.Workflow.Animation.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_WORKFLOW_ANIMATION",
        version_export="gr_animation_version",
        capabilities_export="gr_animation_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Workflow.AnimationRetargeting",
        dll_name="GhostRigger.Core.Workflow.AnimationRetargeting.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_WORKFLOW_ANIMATIONRETARGETING",
        version_export="gr_animation_retargeting_version",
        capabilities_export="gr_animation_retargeting_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Workflow.Retargeting",
        dll_name="GhostRigger.Core.Workflow.Retargeting.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_WORKFLOW_RETARGETING",
        version_export="gr_retargeting_version",
        capabilities_export="gr_retargeting_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Workflow.Characters",
        dll_name="GhostRigger.Core.Workflow.Characters.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_WORKFLOW_CHARACTERS",
        version_export="gr_characters_version",
        capabilities_export="gr_characters_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Scene.Skeleton",
        dll_name="GhostRigger.Core.Scene.Skeleton.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_SCENE_SKELETON",
        version_export="gr_skeleton_version",
        capabilities_export="gr_skeleton_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.IO.File.Format",
        dll_name="GhostRigger.Core.IO.File.Format.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_IO_FILE_FORMAT",
        version_export="gr_mdl_version",
        capabilities_export="gr_mdl_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Math",
        dll_name="GhostRigger.Core.Math.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_MATH",
        version_export="gr_math_version",
        capabilities_export="gr_math_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.GUI.Helpers.Gizmo",
        dll_name="GhostRigger.Core.GUI.Helpers.Gizmo.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_GUI_HELPERS_GIZMO",
        version_export="gr_gizmo_version",
        capabilities_export="gr_gizmo_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Rendering.Textures",
        dll_name="GhostRigger.Core.Rendering.Textures.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_RENDERING_TEXTURES",
        version_export="gr_graphics_version",
        capabilities_export="gr_graphics_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Rendering.Lighting",
        dll_name="GhostRigger.Core.Rendering.Lighting.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_RENDERING_LIGHTING",
        version_export="gr_lighting_version",
        capabilities_export="gr_lighting_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Scene.Walkmesh",
        dll_name="GhostRigger.Core.Scene.Walkmesh.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_SCENE_WALKMESH",
        version_export="gr_walkmesh_version",
        capabilities_export="gr_walkmesh_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Validation",
        dll_name="GhostRigger.Core.Validation.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_VALIDATION",
        version_export="gr_validation_version",
        capabilities_export="gr_validation_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Project",
        dll_name="GhostRigger.Core.Project.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_PROJECT",
        version_export="gr_project_version",
        capabilities_export="gr_project_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Resources.Assets",
        dll_name="GhostRigger.Core.Resources.Assets.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_RESOURCES_ASSETS",
        version_export="gr_assets_version",
        capabilities_export="gr_assets_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Resources",
        dll_name="GhostRigger.Core.Resources.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_RESOURCES",
        version_export="gr_resources_version",
        capabilities_export="gr_resources_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Resources.GameLibrary",
        dll_name="GhostRigger.Core.Resources.GameLibrary.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_RESOURCES_GAMELIBRARY",
        version_export="gr_game_library_version",
        capabilities_export="gr_game_library_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.IO.Export",
        dll_name="GhostRigger.Core.IO.Export.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_IO_EXPORT",
        version_export="gr_export_version",
        capabilities_export="gr_export_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Resources.Game",
        dll_name="GhostRigger.Core.Resources.Game.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_RESOURCES_GAME",
        version_export="gr_game_version",
        capabilities_export="gr_game_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Rendering.Ports",
        dll_name="GhostRigger.Core.Rendering.Ports.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_RENDERING_PORTS",
        version_export="gr_ports_version",
        capabilities_export="gr_ports_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Rendering",
        dll_name="GhostRigger.Core.Rendering.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_RENDERING",
        version_export="gr_rendering_version",
        capabilities_export="gr_rendering_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Runtime.Core.Diagnostics",
        dll_name="GhostRigger.Runtime.Core.Diagnostics.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_RUNTIME_CORE_DIAGNOSTICS",
        version_export="gr_diagnostics_version",
        capabilities_export="gr_diagnostics_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Tools.Special",
        dll_name="GhostRigger.Core.Tools.Special.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_TOOLS_SPECIAL",
        version_export="gr_special_version",
        capabilities_export="gr_special_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Workflow",
        dll_name="GhostRigger.Core.Workflow.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_WORKFLOW",
        version_export="gr_workflow_version",
        capabilities_export="gr_workflow_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Automation",
        dll_name="GhostRigger.Core.Automation.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_AUTOMATION",
        version_export="gr_ipc_version",
        capabilities_export="gr_ipc_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.IO.File.Conversion",
        dll_name="GhostRigger.Core.IO.File.Conversion.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_IO_FILE_CONVERSION",
        version_export="gr_converters_version",
        capabilities_export="gr_converters_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Workflow.Autorig",
        dll_name="GhostRigger.Core.Workflow.Autorig.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_WORKFLOW_AUTORIG",
        version_export="gr_autorig_version",
        capabilities_export="gr_autorig_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Bridge",
        dll_name="GhostRigger.Core.Bridge.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_BRIDGE",
        version_export="gr_core_bridge_ipc_version",
        capabilities_export="gr_core_bridge_ipc_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Tools.Workbench",
        dll_name="GhostRigger.Core.Tools.Workbench.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_TOOLS_WORKBENCH",
        version_export="gr_workbench_version",
        capabilities_export="gr_workbench_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Tools.Mesh",
        dll_name="GhostRigger.Core.Tools.Mesh.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_TOOLS_MESH",
        version_export="gr_mesh_tools_version",
        capabilities_export="gr_mesh_tools_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Runtime.Core.Infrastructure",
        dll_name="GhostRigger.Runtime.Core.Infrastructure.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_RUNTIME_CORE_INFRASTRUCTURE",
        version_export="gr_infra_version",
        capabilities_export="gr_infra_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.IO.File.Write",
        dll_name="GhostRigger.Core.IO.File.Write.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_IO_FILE_WRITE",
        version_export="gr_core_io_files_version",
        capabilities_export="gr_core_io_files_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Rendering.GPU",
        dll_name="GhostRigger.Core.Rendering.GPU.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_RENDERING_GPU",
        version_export="gr_core_rendering_gpu_version",
        capabilities_export="gr_core_rendering_gpu_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Qt.Autorig",
        dll_name="GhostRigger.Core.Qt.Autorig.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_QT_AUTORIG",
        version_export="gr_core_qt_autorig_version",
        capabilities_export="gr_core_qt_autorig_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.Qt.Viewport",
        dll_name="GhostRigger.Core.Qt.Viewport.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_QT_VIEWPORT",
        version_export="gr_core_qt_viewport_version",
        capabilities_export="gr_core_qt_viewport_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.GUI.Display.Dialogs",
        dll_name="GhostRigger.Core.GUI.Display.Dialogs.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_GUI_DISPLAY_DIALOGS",
        version_export="gr_gui_dialogs_version",
        capabilities_export="gr_gui_dialogs_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.GUI.Display.Panels",
        dll_name="GhostRigger.Core.GUI.Display.Panels.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_GUI_DISPLAY_PANELS",
        version_export="gr_gui_panels_version",
        capabilities_export="gr_gui_panels_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.GUI.Display.Viewports",
        dll_name="GhostRigger.Core.GUI.Display.Viewports.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_GUI_DISPLAY_VIEWPORTS",
        version_export="gr_gui_viewports_version",
        capabilities_export="gr_gui_viewports_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.GUI.Display.Theme",
        dll_name="GhostRigger.Core.GUI.Display.Theme.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_GUI_DISPLAY_THEME",
        version_export="gr_gui_theme_version",
        capabilities_export="gr_gui_theme_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.GUI.Display.Rendering",
        dll_name="GhostRigger.Core.GUI.Display.Rendering.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_GUI_DISPLAY_RENDERING",
        version_export="gr_gui_rendering_version",
        capabilities_export="gr_gui_rendering_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.GUI.Display.Lighting",
        dll_name="GhostRigger.Core.GUI.Display.Lighting.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_GUI_DISPLAY_LIGHTING",
        version_export="gr_gui_lighting_version",
        capabilities_export="gr_gui_lighting_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.GUI.Display.Overlays.Gizmo",
        dll_name="GhostRigger.Core.GUI.Display.Overlays.Gizmo.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_GUI_DISPLAY_OVERLAYS_GIZMO",
        version_export="gr_gui_gizmo_version",
        capabilities_export="gr_gui_gizmo_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.GUI.Display.Textures",
        dll_name="GhostRigger.Core.GUI.Display.Textures.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_GUI_DISPLAY_TEXTURES",
        version_export="gr_gui_textures_version",
        capabilities_export="gr_gui_textures_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.GUI.Display.SequenceEditor",
        dll_name="GhostRigger.Core.GUI.Display.SequenceEditor.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_GUI_DISPLAY_SEQUENCEEDITOR",
        version_export="gr_gui_sequence_editor_version",
        capabilities_export="gr_gui_sequence_editor_capabilities_json",
    ),
    NativePackageSpec(
        name="GhostRigger.Core.GUI.Display.Integration",
        dll_name="GhostRigger.Core.GUI.Display.Integration.dll",
        env_var="GHOSTRIGGER_GHOSTRIGGER_CORE_GUI_DISPLAY_INTEGRATION",
        version_export="gr_gui_integration_version",
        capabilities_export="gr_gui_integration_capabilities_json",
    ),
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
        candidates: list[Path] = []
        for path in search_paths:
            candidate = Path(path)
            if candidate.is_dir():
                candidates.extend(candidate / dll_name for dll_name in _dll_names_for_spec(spec))
            else:
                candidates.append(candidate)
        return candidates

    override = os.environ.get(spec.env_var) if spec.env_var else ""
    if override:
        return [Path(override)]

    repo_root = Path(__file__).resolve().parents[3]
    dll_names = _dll_names_for_spec(spec)
    return [directory / dll_name for directory in _candidate_output_dirs(repo_root) for dll_name in dll_names]


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


def query_windows_level_editor_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(WINDOWS_LEVEL_EDITOR_PACKAGE, search_paths)


def query_windows_animation_retarget_workbench_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(WINDOWS_ANIMATION_RETARGET_WORKBENCH_PACKAGE, search_paths)


def query_windows_legacy_rigging_window_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(WINDOWS_LEGACY_RIGGING_WINDOW_PACKAGE, search_paths)


def query_windows_unreal_animator_window_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(WINDOWS_UNREAL_ANIMATOR_WINDOW_PACKAGE, search_paths)


def query_python_module_package_statuses(
    search_paths: Iterable[Path] | None = None,
) -> tuple[NativePackageStatus, ...]:
    return tuple(
        query_native_package_status(spec, search_paths)
        for spec in PYTHON_MODULE_PACKAGE_SPECS
    )


def python_module_package_specs() -> tuple[NativePackageSpec, ...]:
    return PYTHON_MODULE_PACKAGE_SPECS

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
