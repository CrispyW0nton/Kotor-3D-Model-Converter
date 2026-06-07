from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "native" / "templates"


def _render_template(path: Path) -> str:
    values = {
        "{{PROJECT_NAME}}": "GhostRiggerExamplePackage",
        "{{PROJECT_GUID}}": "{11111111-2222-3333-4444-555555555555}",
        "{{ROOT_NAMESPACE}}": "GhostRiggerExamplePackage",
        "{{EXPORT_DEFINE}}": "GHOSTRIGGER_EXAMPLE_PACKAGE_EXPORTS",
        "{{PACKAGE_PROJECT_NAME}}": "GhostRiggerExamplePackage",
        "{{PACKAGE_PROJECT_GUID}}": "{11111111-2222-3333-4444-555555555555}",
    }
    text = path.read_text(encoding="utf-8")
    for token, value in values.items():
        text = text.replace(token, value)
    return text


def test_native_vcxproj_templates_parse_after_token_substitution() -> None:
    for template in TEMPLATE_DIR.glob("*.vcxproj.template"):
        rendered = _render_template(template)
        assert "{{" not in rendered
        ET.fromstring(rendered)


def test_native_template_readme_names_required_phase_one_metadata() -> None:
    readme = (TEMPLATE_DIR / "README.md").read_text(encoding="utf-8")

    assert "GhostRigger.Native" in readme
    assert "GhostRigger.Native.NativeCore" in readme
    assert "GhostRigger.Native.NativeCore.Diagnostics" in (ROOT / "native" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "GhostRigger.Native.NativeCore.Math" in (ROOT / "native" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "GhostRigger.Runtime" in readme
    assert "GhostRigger.Native.NativeCore.{System}" in readme
    assert "GhostRigger.Runtime.Shared.{System}" in readme
    assert "GhostRigger.Tools.{Toolname}" in readme
    assert "GhostRigger.Windows.MainWindow" in readme
    assert "GhostRigger.Runtime.Shared.Descriptors" in (ROOT / "native" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "GhostRigger.Runtime.Shared.Resources" in (ROOT / "native" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "GhostRigger.Renderer.Contracts" in (ROOT / "native" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "GhostRigger.Renderer.Null" in (ROOT / "native" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "GhostRigger.Renderer.D3D12" in (ROOT / "native" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "Owner surface" in readme
    assert "Owner package" in readme
    assert "Bridge method" in readme
    assert "Owner: LordVaderCW" in readme
    assert "Intersects:" in readme


def test_native_docs_define_toolbox_and_window_project_naming() -> None:
    docs = "\n".join(
        [
            (ROOT / "native" / "README.md").read_text(encoding="utf-8"),
            (ROOT / "knowledge_base" / "cpp_integration_phases.md").read_text(encoding="utf-8"),
            (ROOT / "knowledge_base" / "native_migration_plan.md").read_text(encoding="utf-8"),
        ]
    )

    assert "GhostRigger.Tools.{Toolname}" in docs
    assert "GhostRigger.Tools.Retargeting" in docs
    assert "GhostRigger.Windows.MainWindow" in docs


def test_native_toolbox_window_migration_candidates_define_first_phase_one_surfaces() -> None:
    candidates = (
        ROOT / "knowledge_base" / "native_toolbox_window_migration_candidates.md"
    ).read_text(encoding="utf-8")

    assert "GhostRigger.Tools.Retargeting" in candidates
    assert "GhostRigger.Tools.Export" in candidates
    assert "GhostRigger.Tools.CharacterBuilder" in candidates
    assert "GhostRigger.Windows.MainWindow" in candidates
    assert "Owner surface: Retarget Workbench" in candidates
    assert "Owner surface: Export and validation workflow" in candidates
    assert "Owner surface: Character Studio" in candidates
    assert "Owner surface: Main window composition shell" in candidates
    assert "Visible app check: required only when" in candidates


def test_native_dll_template_keeps_release_output_shippable_only() -> None:
    template = (TEMPLATE_DIR / "native_dll.vcxproj.template").read_text(encoding="utf-8")

    assert "<GenerateDebugInformation>false</GenerateDebugInformation>" in template
    assert "$(TargetDir)$(TargetName).pdb" in template
    assert "$(TargetDir)$(TargetName).exp" in template


def test_native_template_readme_documents_release_output_rule() -> None:
    readme = (TEMPLATE_DIR / "README.md").read_text(encoding="utf-8")

    assert "Release output contains only `.exe`, `.dll`, and `.lib` files" in readme
    assert "must not have `Release|Win32.Build.0`" in readme


def test_native_host_project_emits_product_executable_name() -> None:
    project_path = ROOT / "native" / "GhostRigger.Native" / "GhostRigger.Native.vcxproj"
    tree = ET.parse(project_path)
    ns = {"msb": "http://schemas.microsoft.com/developer/msbuild/2003"}

    target_names = [node.text for node in tree.findall(".//msb:TargetName", ns)]

    assert target_names == ["GhostRigger"]


def test_native_host_embedded_program_name_matches_product_executable() -> None:
    main_cpp = (ROOT / "native" / "GhostRigger.Native" / "main.cpp").read_text(encoding="utf-8")

    assert 'L"GhostRigger.exe"' in main_cpp
    assert 'L"GhostRigger.Native.exe"' not in main_cpp


def test_native_core_diagnostics_project_uses_phase_one_naming_and_release_hygiene() -> None:
    project_path = (
        ROOT
        / "native"
        / "GhostRigger.Native.NativeCore.Diagnostics"
        / "GhostRigger.Native.NativeCore.Diagnostics.vcxproj"
    )
    tree = ET.parse(project_path)
    ns = {"msb": "http://schemas.microsoft.com/developer/msbuild/2003"}

    target_names = [node.text for node in tree.findall(".//msb:TargetName", ns)]
    project_refs = [node.attrib["Include"] for node in tree.findall(".//msb:ProjectReference", ns)]
    release_debug_info = tree.findall(
        ".//msb:ItemDefinitionGroup[@Condition=\"'$(Configuration)'=='Release'\"]"
        "/msb:Link/msb:GenerateDebugInformation",
        ns,
    )
    post_build_commands = [
        node.text or "" for node in tree.findall(".//msb:PostBuildEvent/msb:Command", ns)
    ]

    assert target_names == ["GhostRigger.Native.NativeCore.Diagnostics"]
    assert any("GhostRigger.Native.NativeCore.vcxproj" in ref for ref in project_refs)
    assert [node.text for node in release_debug_info] == ["false"]
    assert any("$(TargetDir)$(TargetName).pdb" in command for command in post_build_commands)
    assert any("$(TargetDir)$(TargetName).exp" in command for command in post_build_commands)


def test_native_core_math_project_uses_phase_one_naming_and_release_hygiene() -> None:
    project_path = (
        ROOT
        / "native"
        / "GhostRigger.Native.NativeCore.Math"
        / "GhostRigger.Native.NativeCore.Math.vcxproj"
    )
    tree = ET.parse(project_path)
    ns = {"msb": "http://schemas.microsoft.com/developer/msbuild/2003"}

    target_names = [node.text for node in tree.findall(".//msb:TargetName", ns)]
    project_refs = [node.attrib["Include"] for node in tree.findall(".//msb:ProjectReference", ns)]
    release_debug_info = tree.findall(
        ".//msb:ItemDefinitionGroup[@Condition=\"'$(Configuration)'=='Release'\"]"
        "/msb:Link/msb:GenerateDebugInformation",
        ns,
    )
    post_build_commands = [
        node.text or "" for node in tree.findall(".//msb:PostBuildEvent/msb:Command", ns)
    ]

    assert target_names == ["GhostRigger.Native.NativeCore.Math"]
    assert any("GhostRigger.Native.NativeCore.vcxproj" in ref for ref in project_refs)
    assert [node.text for node in release_debug_info] == ["false"]
    assert any("$(TargetDir)$(TargetName).pdb" in command for command in post_build_commands)
    assert any("$(TargetDir)$(TargetName).exp" in command for command in post_build_commands)


def test_runtime_shared_descriptors_project_uses_phase_one_naming_and_release_hygiene() -> None:
    project_path = (
        ROOT
        / "native"
        / "GhostRigger.Runtime.Shared.Descriptors"
        / "GhostRigger.Runtime.Shared.Descriptors.vcxproj"
    )
    tree = ET.parse(project_path)
    ns = {"msb": "http://schemas.microsoft.com/developer/msbuild/2003"}

    target_names = [node.text for node in tree.findall(".//msb:TargetName", ns)]
    project_refs = [node.attrib["Include"] for node in tree.findall(".//msb:ProjectReference", ns)]
    release_debug_info = tree.findall(
        ".//msb:ItemDefinitionGroup[@Condition=\"'$(Configuration)'=='Release'\"]"
        "/msb:Link/msb:GenerateDebugInformation",
        ns,
    )
    post_build_commands = [
        node.text or "" for node in tree.findall(".//msb:PostBuildEvent/msb:Command", ns)
    ]

    assert target_names == ["GhostRigger.Runtime.Shared.Descriptors"]
    assert any("GhostRigger.Native.NativeCore.vcxproj" in ref for ref in project_refs)
    assert [node.text for node in release_debug_info] == ["false"]
    assert any("$(TargetDir)$(TargetName).pdb" in command for command in post_build_commands)
    assert any("$(TargetDir)$(TargetName).exp" in command for command in post_build_commands)


def test_runtime_shared_resources_project_uses_phase_one_naming_and_release_hygiene() -> None:
    project_path = (
        ROOT
        / "native"
        / "GhostRigger.Runtime.Shared.Resources"
        / "GhostRigger.Runtime.Shared.Resources.vcxproj"
    )
    tree = ET.parse(project_path)
    ns = {"msb": "http://schemas.microsoft.com/developer/msbuild/2003"}

    target_names = [node.text for node in tree.findall(".//msb:TargetName", ns)]
    project_refs = [node.attrib["Include"] for node in tree.findall(".//msb:ProjectReference", ns)]
    release_debug_info = tree.findall(
        ".//msb:ItemDefinitionGroup[@Condition=\"'$(Configuration)'=='Release'\"]"
        "/msb:Link/msb:GenerateDebugInformation",
        ns,
    )
    post_build_commands = [
        node.text or "" for node in tree.findall(".//msb:PostBuildEvent/msb:Command", ns)
    ]

    assert target_names == ["GhostRigger.Runtime.Shared.Resources"]
    assert any("GhostRigger.Native.NativeCore.vcxproj" in ref for ref in project_refs)
    assert [node.text for node in release_debug_info] == ["false"]
    assert any("$(TargetDir)$(TargetName).pdb" in command for command in post_build_commands)
    assert any("$(TargetDir)$(TargetName).exp" in command for command in post_build_commands)


def test_renderer_contracts_project_uses_phase_one_naming_and_release_hygiene() -> None:
    project_path = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.Contracts"
        / "GhostRigger.Renderer.Contracts.vcxproj"
    )
    tree = ET.parse(project_path)
    ns = {"msb": "http://schemas.microsoft.com/developer/msbuild/2003"}

    target_names = [node.text for node in tree.findall(".//msb:TargetName", ns)]
    project_refs = [node.attrib["Include"] for node in tree.findall(".//msb:ProjectReference", ns)]
    release_debug_info = tree.findall(
        ".//msb:ItemDefinitionGroup[@Condition=\"'$(Configuration)'=='Release'\"]"
        "/msb:Link/msb:GenerateDebugInformation",
        ns,
    )
    post_build_commands = [
        node.text or "" for node in tree.findall(".//msb:PostBuildEvent/msb:Command", ns)
    ]

    assert target_names == ["GhostRigger.Renderer.Contracts"]
    assert any("GhostRigger.Native.NativeCore.vcxproj" in ref for ref in project_refs)
    assert [node.text for node in release_debug_info] == ["false"]
    assert any("$(TargetDir)$(TargetName).pdb" in command for command in post_build_commands)
    assert any("$(TargetDir)$(TargetName).exp" in command for command in post_build_commands)


def test_renderer_null_project_uses_phase_one_naming_and_release_hygiene() -> None:
    project_path = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.Null"
        / "GhostRigger.Renderer.Null.vcxproj"
    )
    tree = ET.parse(project_path)
    ns = {"msb": "http://schemas.microsoft.com/developer/msbuild/2003"}

    target_names = [node.text for node in tree.findall(".//msb:TargetName", ns)]
    project_refs = [node.attrib["Include"] for node in tree.findall(".//msb:ProjectReference", ns)]
    release_debug_info = tree.findall(
        ".//msb:ItemDefinitionGroup[@Condition=\"'$(Configuration)'=='Release'\"]"
        "/msb:Link/msb:GenerateDebugInformation",
        ns,
    )
    post_build_commands = [
        node.text or "" for node in tree.findall(".//msb:PostBuildEvent/msb:Command", ns)
    ]

    assert target_names == ["GhostRigger.Renderer.Null"]
    assert any("GhostRigger.Renderer.Contracts.vcxproj" in ref for ref in project_refs)
    assert [node.text for node in release_debug_info] == ["false"]
    assert any("$(TargetDir)$(TargetName).pdb" in command for command in post_build_commands)
    assert any("$(TargetDir)$(TargetName).exp" in command for command in post_build_commands)


def test_renderer_d3d12_project_uses_phase_one_naming_and_release_hygiene() -> None:
    project_path = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.D3D12"
        / "GhostRigger.Renderer.D3D12.vcxproj"
    )
    tree = ET.parse(project_path)
    ns = {"msb": "http://schemas.microsoft.com/developer/msbuild/2003"}

    target_names = [node.text for node in tree.findall(".//msb:TargetName", ns)]
    project_refs = [node.attrib["Include"] for node in tree.findall(".//msb:ProjectReference", ns)]
    release_debug_info = tree.findall(
        ".//msb:ItemDefinitionGroup[@Condition=\"'$(Configuration)'=='Release'\"]"
        "/msb:Link/msb:GenerateDebugInformation",
        ns,
    )
    post_build_commands = [
        node.text or "" for node in tree.findall(".//msb:PostBuildEvent/msb:Command", ns)
    ]
    link_dependencies = [
        node.text or "" for node in tree.findall(".//msb:Link/msb:AdditionalDependencies", ns)
    ]

    assert target_names == ["GhostRigger.Renderer.D3D12"]
    assert any("GhostRigger.Renderer.Contracts.vcxproj" in ref for ref in project_refs)
    assert [node.text for node in release_debug_info] == ["false"]
    assert any("d3d12.lib" in dependencies for dependencies in link_dependencies)
    assert any("dxgi.lib" in dependencies for dependencies in link_dependencies)
    assert any("$(TargetDir)$(TargetName).pdb" in command for command in post_build_commands)
    assert any("$(TargetDir)$(TargetName).exp" in command for command in post_build_commands)


def test_renderer_d3d12_exports_descriptor_allocator_readiness_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
    ).read_text(encoding="utf-8")
    validator = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.D3D12.DEBUG"
        / "GhostRiggerRendererD3D12DEBUG.cpp"
    ).read_text(encoding="utf-8")

    assert "gr_renderer_d3d12_descriptor_allocator_readiness_json" in header
    assert "renderer_d3d12_descriptor_allocator_readiness.v1" in implementation
    assert "CreateDescriptorHeap" in implementation
    assert "CreateCommandAllocator" in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert "gr_renderer_d3d12_descriptor_allocator_readiness_json(context)" in validator


def test_renderer_d3d12_exports_command_list_readiness_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
    ).read_text(encoding="utf-8")
    validator = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.D3D12.DEBUG"
        / "GhostRiggerRendererD3D12DEBUG.cpp"
    ).read_text(encoding="utf-8")

    assert "gr_renderer_d3d12_command_list_readiness_json" in header
    assert "renderer_d3d12_command_list_readiness.v1" in implementation
    assert "CreateCommandList" in implementation
    assert "command_list->Close()" in implementation
    assert '"app_commands_recorded":false' in implementation
    assert '"command_list_executed":false' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert "gr_renderer_d3d12_command_list_readiness_json(context)" in validator


def test_renderer_d3d12_exports_surface_swap_chain_readiness_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
    ).read_text(encoding="utf-8")
    validator = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.D3D12.DEBUG"
        / "GhostRiggerRendererD3D12DEBUG.cpp"
    ).read_text(encoding="utf-8")

    assert "gr_renderer_d3d12_surface_swap_chain_readiness_json" in header
    assert "renderer_d3d12_surface_swap_chain_readiness.v1" in implementation
    assert '"surface_handle_type":"HWND"' in implementation
    assert '"native_window_handle_ready":false' in implementation
    assert '"swap_chain_created":false' in implementation
    assert '"present_enabled":false' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert "gr_renderer_d3d12_surface_swap_chain_readiness_json(context, nullptr)" in validator


def test_renderer_d3d12_exports_render_target_metadata_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
    ).read_text(encoding="utf-8")
    validator = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.D3D12.DEBUG"
        / "GhostRiggerRendererD3D12DEBUG.cpp"
    ).read_text(encoding="utf-8")

    assert "gr_renderer_d3d12_render_target_metadata_json" in header
    assert "renderer_d3d12_render_target_metadata.v1" in implementation
    assert "D3D12_DESCRIPTOR_HEAP_TYPE_RTV" in implementation
    assert '"expected_back_buffer_count":2' in implementation
    assert '"back_buffers_acquired":false' in implementation
    assert '"render_target_views_created":false' in implementation
    assert '"present_enabled":false' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert "gr_renderer_d3d12_render_target_metadata_json(context)" in validator


def test_renderer_d3d12_exports_barrier_clear_pass_metadata_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
    ).read_text(encoding="utf-8")
    validator = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.D3D12.DEBUG"
        / "GhostRiggerRendererD3D12DEBUG.cpp"
    ).read_text(encoding="utf-8")

    assert "gr_renderer_d3d12_barrier_clear_pass_metadata_json" in header
    assert "renderer_d3d12_barrier_clear_pass_metadata.v1" in implementation
    assert '"D3D12_RESOURCE_STATE_PRESENT"' in implementation
    assert '"D3D12_RESOURCE_STATE_RENDER_TARGET"' in implementation
    assert '"resource_barriers_recorded":false' in implementation
    assert '"clear_recorded":false' in implementation
    assert '"command_list_executed":false' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert "gr_renderer_d3d12_barrier_clear_pass_metadata_json(context)" in validator


def test_renderer_d3d12_exports_command_recording_dry_run_frame_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
    ).read_text(encoding="utf-8")
    validator = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.D3D12.DEBUG"
        / "GhostRiggerRendererD3D12DEBUG.cpp"
    ).read_text(encoding="utf-8")

    assert "gr_renderer_d3d12_command_recording_dry_run_frame_json" in header
    assert "renderer_d3d12_command_recording_dry_run_frame.v1" in implementation
    assert '"command_allocator_reset":false' in implementation
    assert '"command_list_reset":false' in implementation
    assert '"draw_calls_recorded":0' in implementation
    assert '"command_list_executed":false' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert "gr_renderer_d3d12_command_recording_dry_run_frame_json(context)" in validator


def test_renderer_d3d12_exports_guarded_command_recording_diagnostics_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
    ).read_text(encoding="utf-8")
    validator = (
        ROOT
        / "native"
        / "GhostRigger.Renderer.D3D12.DEBUG"
        / "GhostRiggerRendererD3D12DEBUG.cpp"
    ).read_text(encoding="utf-8")

    assert "gr_renderer_d3d12_guarded_command_recording_diagnostics_json" in header
    assert "renderer_d3d12_guarded_command_recording_diagnostics.v1" in implementation
    assert "command_allocator->Reset()" in implementation
    assert "command_list->Reset" in implementation
    assert "command_list->Close()" in implementation
    assert '"draw_calls_recorded":0' in implementation
    assert '"command_list_executed":false' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert "gr_renderer_d3d12_guarded_command_recording_diagnostics_json(context)" in validator


def test_native_debug_validator_projects_are_not_built_in_release() -> None:
    solution = (ROOT / "GhostRigger.sln").read_text(encoding="utf-8")

    debug_project_guids = {
        "{C03C45BD-2AF3-471B-A83E-24B4AF17F002}",
        "{C5E47C3A-7F3E-44A2-AF9A-C50346CB76B2}",
        "{19928EC9-FCAB-4DC0-B798-5512563F99D6}",
        "{3F23681A-26CC-4C2D-B4F3-C766223FE004}",
        "{15144CB5-C12B-4183-951F-4CE841E89B9B}",
        "{243B0BA6-B5CA-4DB7-8131-09158549818A}",
        "{672F0576-76BB-4A46-AB34-2AEE67CC9CBB}",
        "{3309ACB6-2BE0-4C54-BA13-412310A65888}",
        "{6BAA4B32-55DD-4A3B-8440-C15A47B83423}",
        "{B56D386B-6E3A-48F7-A2FE-166B8D2AA730}",
    }

    for guid in debug_project_guids:
        assert f"{guid}.Release|Win32.Build.0" not in solution
        assert f"{guid}.Release|x64.Build.0" not in solution
