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


def test_tools_retargeting_project_scaffold_matches_phase_one_boundary() -> None:
    solution = (ROOT / "GhostRigger.sln").read_text(encoding="utf-8")
    project = (
        ROOT
        / "native"
        / "GhostRigger.Tools.Retargeting"
        / "GhostRigger.Tools.Retargeting.vcxproj"
    ).read_text(encoding="utf-8")
    debug_project = (
        ROOT
        / "native"
        / "GhostRigger.Tools.Retargeting.DEBUG"
        / "GhostRigger.Tools.Retargeting.DEBUG.vcxproj"
    ).read_text(encoding="utf-8")
    readme = (
        ROOT
        / "native"
        / "GhostRigger.Tools.Retargeting"
        / "README.md"
    ).read_text(encoding="utf-8")

    assert "GhostRigger.Tools.Retargeting" in solution
    assert "GhostRigger.Tools.Retargeting.DEBUG" in solution
    assert "<TargetName>GhostRigger.Tools.Retargeting</TargetName>" in project
    assert "GHOSTRIGGER_TOOLS_RETARGETING_EXPORTS" in project
    assert "<TargetName>GhostRigger.Tools.Retargeting.DEBUG</TargetName>" in debug_project
    assert "Owner surface: Retarget Workbench" in readme
    assert "Bridge method: C ABI DLL" in readme


def test_tools_retargeting_exports_diagnostic_c_abi_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Tools.Retargeting"
        / "GhostRiggerToolsRetargeting.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Tools.Retargeting"
        / "GhostRiggerToolsRetargeting.cpp"
    ).read_text(encoding="utf-8")
    validator = (
        ROOT
        / "native"
        / "GhostRigger.Tools.Retargeting.DEBUG"
        / "GhostRiggerToolsRetargetingDEBUG.cpp"
    ).read_text(encoding="utf-8")

    assert "gr_tools_retargeting_version" in header
    assert "gr_tools_retargeting_capabilities_json" in header
    assert "gr_tools_retargeting_owner_boundary_json" in header
    assert "gr_tools_retargeting_solve_packet_schema_json" in header
    assert '"tool_package":true' in implementation
    assert '"owner_surface":"Retarget Workbench"' in implementation
    assert '"bridge_method":"C ABI DLL"' in implementation
    assert '"native_solve_enabled":false' in implementation
    assert '"python_fallback_required":true' in implementation
    assert "tools_retargeting_owner_boundary.v1" in implementation
    assert "tools_retargeting_solve_packet_schema.v1" in implementation
    assert '"solve_attempted":false' in implementation
    assert '"solve_result_count":0' in implementation
    assert "gr_tools_retargeting_solve_packet_schema_json()" in validator


def test_tools_export_project_scaffold_matches_phase_one_boundary() -> None:
    solution = (ROOT / "GhostRigger.sln").read_text(encoding="utf-8")
    project = (
        ROOT
        / "native"
        / "GhostRigger.Tools.Export"
        / "GhostRigger.Tools.Export.vcxproj"
    ).read_text(encoding="utf-8")
    debug_project = (
        ROOT
        / "native"
        / "GhostRigger.Tools.Export.DEBUG"
        / "GhostRigger.Tools.Export.DEBUG.vcxproj"
    ).read_text(encoding="utf-8")
    readme = (
        ROOT
        / "native"
        / "GhostRigger.Tools.Export"
        / "README.md"
    ).read_text(encoding="utf-8")

    assert "GhostRigger.Tools.Export" in solution
    assert "GhostRigger.Tools.Export.DEBUG" in solution
    assert "<TargetName>GhostRigger.Tools.Export</TargetName>" in project
    assert "GHOSTRIGGER_TOOLS_EXPORT_EXPORTS" in project
    assert "<TargetName>GhostRigger.Tools.Export.DEBUG</TargetName>" in debug_project
    assert "Owner surface: Export and validation workflow" in readme
    assert "Bridge method: C ABI DLL" in readme


def test_tools_export_exports_diagnostic_c_abi_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Tools.Export"
        / "GhostRiggerToolsExport.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Tools.Export"
        / "GhostRiggerToolsExport.cpp"
    ).read_text(encoding="utf-8")
    validator = (
        ROOT
        / "native"
        / "GhostRigger.Tools.Export.DEBUG"
        / "GhostRiggerToolsExportDEBUG.cpp"
    ).read_text(encoding="utf-8")

    assert "gr_tools_export_version" in header
    assert "gr_tools_export_capabilities_json" in header
    assert "gr_tools_export_owner_boundary_json" in header
    assert "gr_tools_export_preflight_packet_schema_json" in header
    assert '"tool_package":true' in implementation
    assert '"owner_surface":"Export and validation workflow"' in implementation
    assert '"bridge_method":"C ABI DLL"' in implementation
    assert '"native_write_enabled":false' in implementation
    assert '"python_fallback_required":true' in implementation
    assert "tools_export_owner_boundary.v1" in implementation
    assert "tools_export_preflight_packet_schema.v1" in implementation
    assert '"preflight_attempted":false' in implementation
    assert '"preflight_result_count":0' in implementation
    assert "gr_tools_export_preflight_packet_schema_json()" in validator


def test_tools_character_builder_project_scaffold_matches_phase_one_boundary() -> None:
    solution = (ROOT / "GhostRigger.sln").read_text(encoding="utf-8")
    project = (
        ROOT
        / "native"
        / "GhostRigger.Tools.CharacterBuilder"
        / "GhostRigger.Tools.CharacterBuilder.vcxproj"
    ).read_text(encoding="utf-8")
    debug_project = (
        ROOT
        / "native"
        / "GhostRigger.Tools.CharacterBuilder.DEBUG"
        / "GhostRigger.Tools.CharacterBuilder.DEBUG.vcxproj"
    ).read_text(encoding="utf-8")
    readme = (
        ROOT
        / "native"
        / "GhostRigger.Tools.CharacterBuilder"
        / "README.md"
    ).read_text(encoding="utf-8")

    assert "GhostRigger.Tools.CharacterBuilder" in solution
    assert "GhostRigger.Tools.CharacterBuilder.DEBUG" in solution
    assert "<TargetName>GhostRigger.Tools.CharacterBuilder</TargetName>" in project
    assert "GHOSTRIGGER_TOOLS_CHARACTER_BUILDER_EXPORTS" in project
    assert "<TargetName>GhostRigger.Tools.CharacterBuilder.DEBUG</TargetName>" in debug_project
    assert "Owner surface: Character Studio" in readme
    assert "Bridge method: C ABI DLL" in readme


def test_tools_character_builder_exports_diagnostic_c_abi_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Tools.CharacterBuilder"
        / "GhostRiggerToolsCharacterBuilder.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Tools.CharacterBuilder"
        / "GhostRiggerToolsCharacterBuilder.cpp"
    ).read_text(encoding="utf-8")
    validator = (
        ROOT
        / "native"
        / "GhostRigger.Tools.CharacterBuilder.DEBUG"
        / "GhostRiggerToolsCharacterBuilderDEBUG.cpp"
    ).read_text(encoding="utf-8")

    assert "gr_tools_character_builder_version" in header
    assert "gr_tools_character_builder_capabilities_json" in header
    assert "gr_tools_character_builder_owner_boundary_json" in header
    assert "gr_tools_character_builder_autofit_packet_schema_json" in header
    assert '"tool_package":true' in implementation
    assert '"owner_surface":"Character Studio"' in implementation
    assert '"bridge_method":"C ABI DLL"' in implementation
    assert '"native_autofit_enabled":false' in implementation
    assert '"python_fallback_required":true' in implementation
    assert "tools_character_builder_owner_boundary.v1" in implementation
    assert "tools_character_builder_autofit_packet_schema.v1" in implementation
    assert '"autofit_attempted":false' in implementation
    assert '"autofit_result_count":0' in implementation
    assert "gr_tools_character_builder_autofit_packet_schema_json()" in validator


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


def test_renderer_d3d12_capabilities_report_complete_guarded_metadata_surface() -> None:
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

    assert '"draw_submission_enabled":false' in implementation
    assert '"guarded_metadata_capabilities":[' in implementation
    assert '"descriptor_allocator_readiness"' in implementation
    assert '"command_list_readiness"' in implementation
    assert '"surface_swap_chain_readiness"' in implementation
    assert '"guarded_command_recording_diagnostics"' in implementation
    assert '"no_draw_execution_fence_diagnostics"' in implementation
    assert '"guarded_swap_chain_creation_diagnostics"' in implementation
    assert '"guarded_back_buffer_rtv_diagnostics"' in implementation
    assert '"guarded_barrier_clear_recording_diagnostics"' in implementation
    assert '"guarded_clear_pass_execution_fence_diagnostics"' in implementation
    assert '"post_present_frame_accounting_diagnostics"' in implementation
    assert '"guarded_shader_bytecode_metadata"' in implementation
    assert '"shader_reflection_input_layout_metadata"' in implementation
    assert '"guarded_root_signature_metadata"' in implementation
    assert '"guarded_pipeline_state_object_metadata"' in implementation
    assert '"guarded_draw_command_recording_metadata"' in implementation
    assert '"guarded_draw_submission_readiness_metadata"' in implementation
    assert '"guarded_post_draw_frame_accounting_readiness_metadata"' in implementation
    assert '"guarded_post_draw_frame_accounting_readiness_metadata"]})' in implementation
    assert '"guarded_post_draw_frame_accounting_readiness_metadata"])})' not in implementation
    assert '"guarded_metadata_capabilities":[' in validator
    assert '"guarded_post_draw_frame_accounting_readiness_metadata"' in validator


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


def test_renderer_d3d12_exports_no_draw_execution_fence_diagnostics_boundary() -> None:
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

    assert "gr_renderer_d3d12_no_draw_execution_fence_diagnostics_json" in header
    assert "renderer_d3d12_no_draw_execution_fence_diagnostics.v1" in implementation
    assert "ExecuteCommandLists" in implementation
    assert "CreateFence" in implementation
    assert "Signal" in implementation
    assert "SetEventOnCompletion" in implementation
    assert '"no_draw_command_list_executed":false' in implementation
    assert '"draw_calls_recorded":0' in implementation
    assert '"command_lists_submitted":' in implementation
    assert '"present_enabled":false' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert "gr_renderer_d3d12_no_draw_execution_fence_diagnostics_json(context)" in validator


def test_renderer_d3d12_exports_present_readiness_metadata_boundary() -> None:
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

    assert "gr_renderer_d3d12_present_readiness_metadata_json" in header
    assert "renderer_d3d12_present_readiness_metadata.v1" in implementation
    assert '"swap_chain_created":false' in implementation
    assert '"back_buffers_acquired":false' in implementation
    assert '"present_ready":false' in implementation
    assert '"present_called":false' in implementation
    assert '"present_enabled":false' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert '"present_call_disabled"' in implementation
    assert "gr_renderer_d3d12_present_readiness_metadata_json(context)" in validator


def test_renderer_d3d12_exports_guarded_swap_chain_creation_boundary() -> None:
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

    assert "gr_renderer_d3d12_guarded_swap_chain_creation_diagnostics_json" in header
    assert "renderer_d3d12_guarded_swap_chain_creation_diagnostics.v1" in implementation
    assert "CreateSwapChainForHwnd" in implementation
    assert "static_cast<HWND>(native_window_handle)" in implementation
    assert '"native_window_handle_ready":false' in implementation
    assert '"swap_chain_create_attempted":false' in implementation
    assert '"swap_chain_created":false' in implementation
    assert '"back_buffers_acquired":false' in implementation
    assert '"render_target_views_created":false' in implementation
    assert '"present_called":false' in implementation
    assert '"present_enabled":false' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert "gr_renderer_d3d12_guarded_swap_chain_creation_diagnostics_json" in validator


def test_renderer_d3d12_exports_guarded_back_buffer_rtv_boundary() -> None:
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

    assert "gr_renderer_d3d12_guarded_back_buffer_rtv_diagnostics_json" in header
    assert "renderer_d3d12_guarded_back_buffer_rtv_diagnostics.v1" in implementation
    assert "GetBuffer" in implementation
    assert "CreateRenderTargetView" in implementation
    assert '"back_buffer_get_attempted":false' in implementation
    assert '"back_buffers_acquired":false' in implementation
    assert '"render_target_views_created":false' in implementation
    assert '"resource_barriers_recorded":false' in implementation
    assert '"clear_recorded":false' in implementation
    assert '"present_called":false' in implementation
    assert '"present_enabled":false' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert "gr_renderer_d3d12_guarded_back_buffer_rtv_diagnostics_json(context)" in validator


def test_renderer_d3d12_exports_guarded_barrier_clear_recording_boundary() -> None:
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

    assert "gr_renderer_d3d12_guarded_barrier_clear_recording_diagnostics_json" in header
    assert "renderer_d3d12_guarded_barrier_clear_recording_diagnostics.v1" in implementation
    assert "ResourceBarrier" in implementation
    assert "ClearRenderTargetView" in implementation
    assert "D3D12_RESOURCE_STATE_PRESENT" in implementation
    assert "D3D12_RESOURCE_STATE_RENDER_TARGET" in implementation
    assert '"barrier_clear_recording_attempted":false' in implementation
    assert '"resource_barriers_recorded":false' in implementation
    assert '"clear_recorded":false' in implementation
    assert '"command_list_executed":false' in implementation
    assert '"present_called":false' in implementation
    assert '"present_enabled":false' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert "gr_renderer_d3d12_guarded_barrier_clear_recording_diagnostics_json(context)" in validator


def test_renderer_d3d12_exports_guarded_clear_pass_execution_fence_boundary() -> None:
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

    assert "gr_renderer_d3d12_guarded_clear_pass_execution_fence_diagnostics_json" in header
    assert "renderer_d3d12_guarded_clear_pass_execution_fence_diagnostics.v1" in implementation
    assert "ExecuteCommandLists" in implementation
    assert "CreateFence" in implementation
    assert "SetEventOnCompletion" in implementation
    assert '"recorded_clear_pass_ready":false' in implementation
    assert '"clear_pass_command_list_executed":false' in implementation
    assert '"command_lists_submitted":0' in implementation
    assert '"draw_calls_recorded":0' in implementation
    assert '"present_called":false' in implementation
    assert '"present_enabled":false' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert "gr_renderer_d3d12_guarded_clear_pass_execution_fence_diagnostics_json(context)" in validator


def test_renderer_d3d12_exports_post_clear_present_readiness_boundary() -> None:
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

    assert "gr_renderer_d3d12_post_clear_present_readiness_diagnostics_json" in header
    assert "renderer_d3d12_post_clear_present_readiness_diagnostics.v1" in implementation
    assert '"clear_pass_executed":false' in implementation
    assert '"clear_pass_fence_completed":false' in implementation
    assert '"back_buffer_state_expected":"D3D12_RESOURCE_STATE_PRESENT"' in implementation
    assert '"present_ready":false' in implementation
    assert '"present_called":false' in implementation
    assert '"present_enabled":false' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert '"present_call_disabled"' in implementation
    assert "gr_renderer_d3d12_post_clear_present_readiness_diagnostics_json(context)" in validator


def test_renderer_d3d12_exports_guarded_present_call_boundary() -> None:
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

    assert "gr_renderer_d3d12_guarded_present_call_diagnostics_json" in header
    assert "renderer_d3d12_guarded_present_call_diagnostics.v1" in implementation
    assert "target->guarded_swap_chain->Present(0, 0)" in implementation
    assert '"present_ready":false' in implementation
    assert '"present_called":false' in implementation
    assert '"present_succeeded":false' in implementation
    assert '"draw_calls_recorded":0' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert '"present_sync_interval":0' in implementation
    assert '"present_flags":0' in implementation
    assert "gr_renderer_d3d12_guarded_present_call_diagnostics_json(context)" in validator


def test_renderer_d3d12_exports_post_present_frame_accounting_boundary() -> None:
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

    assert "gr_renderer_d3d12_post_present_frame_accounting_diagnostics_json" in header
    assert "renderer_d3d12_post_present_frame_accounting_diagnostics.v1" in implementation
    assert '"frame_presented":false' in implementation
    assert '"frame_index":0' in implementation
    assert '"presented_frame_count":0' in implementation
    assert '"cpu_submit_ms":0.0' in implementation
    assert '"gpu_frame_ms":0.0' in implementation
    assert '"draw_calls_recorded":0' in implementation
    assert '"triangles_submitted":0' in implementation
    assert '"resource_uploads":0' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert "gr_renderer_d3d12_post_present_frame_accounting_diagnostics_json(context)" in validator


def test_renderer_d3d12_exports_draw_list_readiness_metadata_boundary() -> None:
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

    assert "gr_renderer_d3d12_draw_list_readiness_metadata_json" in header
    assert "renderer_d3d12_draw_list_readiness_metadata.v1" in implementation
    assert '"draw_list_ready":false' in implementation
    assert '"draw_list_source":"future_native_payload"' in implementation
    assert '"requires_mesh_handles":true' in implementation
    assert '"requires_material_handles":true' in implementation
    assert '"requires_transform_packets":true' in implementation
    assert '"requires_resource_residency":true' in implementation
    assert '"mesh_handle_count":0' in implementation
    assert '"material_handle_count":0' in implementation
    assert '"draw_command_count":0' in implementation
    assert '"indexed_draw_command_count":0' in implementation
    assert '"instanced_draw_command_count":0' in implementation
    assert '"skinned_draw_command_count":0' in implementation
    assert '"command_list_recorded_for_draws":false' in implementation
    assert '"command_list_executed_for_draws":false' in implementation
    assert '"present_after_draws_enabled":false' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert "gr_renderer_d3d12_draw_list_readiness_metadata_json(context)" in validator


def test_renderer_d3d12_exports_resource_binding_readiness_metadata_boundary() -> None:
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

    assert "gr_renderer_d3d12_resource_binding_readiness_metadata_json" in header
    assert "renderer_d3d12_resource_binding_readiness_metadata.v1" in implementation
    assert '"resource_binding_ready":false' in implementation
    assert '"root_signature_created":false' in implementation
    assert '"pipeline_state_created":false' in implementation
    assert '"descriptor_heaps_set_for_draws":false' in implementation
    assert '"descriptor_tables_bound":false' in implementation
    assert '"vertex_buffers_bound":0' in implementation
    assert '"index_buffers_bound":0' in implementation
    assert '"constant_buffers_bound":0' in implementation
    assert '"shader_resources_bound":0' in implementation
    assert '"samplers_bound":0' in implementation
    assert '"textures_bound":0' in implementation
    assert '"skin_palettes_bound":0' in implementation
    assert '"materials_bound":0' in implementation
    assert '"resource_barriers_for_draws_recorded":false' in implementation
    assert '"command_list_recorded_for_draws":false' in implementation
    assert '"draw_calls_recorded":0' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert "gr_renderer_d3d12_resource_binding_readiness_metadata_json(context)" in validator


def test_renderer_d3d12_exports_pipeline_state_readiness_metadata_boundary() -> None:
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

    assert "gr_renderer_d3d12_pipeline_state_readiness_metadata_json" in header
    assert "renderer_d3d12_pipeline_state_readiness_metadata.v1" in implementation
    assert '"pipeline_state_ready":false' in implementation
    assert '"root_signature_created":false' in implementation
    assert '"root_parameters_declared":0' in implementation
    assert '"descriptor_ranges_declared":0' in implementation
    assert '"static_samplers_declared":0' in implementation
    assert '"pipeline_state_created":false' in implementation
    assert '"input_layout_ready":false' in implementation
    assert '"input_layout_semantics":["POSITION","NORMAL","TEXCOORD","BLENDINDICES","BLENDWEIGHT"]' in implementation
    assert '"vertex_shader_ready":false' in implementation
    assert '"pixel_shader_ready":false' in implementation
    assert '"skinning_shader_variant_ready":false' in implementation
    assert '"sprite_shader_variant_ready":false' in implementation
    assert '"depth_stencil_state_ready":false' in implementation
    assert '"rasterizer_state_ready":false' in implementation
    assert '"blend_state_ready":false' in implementation
    assert '"primitive_topology_type":"D3D12_PRIMITIVE_TOPOLOGY_TYPE_TRIANGLE"' in implementation
    assert '"command_list_recorded_for_draws":false' in implementation
    assert '"draw_calls_recorded":0' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert "gr_renderer_d3d12_pipeline_state_readiness_metadata_json(context)" in validator


def test_renderer_d3d12_exports_guarded_shader_bytecode_metadata_boundary() -> None:
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

    assert "gr_renderer_d3d12_guarded_shader_bytecode_metadata_json" in header
    assert "renderer_d3d12_guarded_shader_bytecode_metadata.v1" in implementation
    assert '"shader_bytecode_ready":false' in implementation
    assert '"shader_compiler_invoked":false' in implementation
    assert '"dxc_compiler_required":true' in implementation
    assert '"legacy_d3dcompile_used":false' in implementation
    assert '"compiled_shader_blob_count":0' in implementation
    assert '"vertex_shader_entry":"VSMain"' in implementation
    assert '"vertex_shader_target":"vs_6_0"' in implementation
    assert '"pixel_shader_entry":"PSMain"' in implementation
    assert '"pixel_shader_target":"ps_6_0"' in implementation
    assert '"vertex_shader_compiled":false' in implementation
    assert '"pixel_shader_compiled":false' in implementation
    assert '"skinning_shader_variant_compiled":false' in implementation
    assert '"sprite_shader_variant_compiled":false' in implementation
    assert '"shader_reflection_ready":false' in implementation
    assert '"input_layout_from_reflection":false' in implementation
    assert '"root_signature_from_shader":false' in implementation
    assert '"pipeline_state_created":false' in implementation
    assert '"draw_calls_recorded":0' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert "D3DCompile(" not in implementation
    assert "DxcCreateInstance" not in implementation
    assert "gr_renderer_d3d12_guarded_shader_bytecode_metadata_json(context)" in validator


def test_renderer_d3d12_exports_shader_reflection_input_layout_metadata_boundary() -> None:
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

    assert "gr_renderer_d3d12_shader_reflection_input_layout_metadata_json" in header
    assert "renderer_d3d12_shader_reflection_input_layout_metadata.v1" in implementation
    assert '"shader_reflection_ready":false' in implementation
    assert '"reflection_api":"DXC reflection"' in implementation
    assert '"reflection_invoked":false' in implementation
    assert '"input_layout_ready":false' in implementation
    assert '"input_layout_from_reflection":false' in implementation
    assert '"input_element_count":0' in implementation
    assert '"semantic":"POSITION"' in implementation
    assert '"semantic":"NORMAL"' in implementation
    assert '"semantic":"TEXCOORD"' in implementation
    assert '"semantic":"BLENDINDICES"' in implementation
    assert '"semantic":"BLENDWEIGHT"' in implementation
    assert '"actual_input_elements":[]' in implementation
    assert '"vertex_stride_bytes":0' in implementation
    assert '"skinned_vertex_stride_bytes":0' in implementation
    assert '"root_signature_from_reflection":false' in implementation
    assert '"pipeline_state_created":false' in implementation
    assert '"draw_calls_recorded":0' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert "D3DReflect(" not in implementation
    assert "ID3D12ShaderReflection" not in implementation
    assert "gr_renderer_d3d12_shader_reflection_input_layout_metadata_json(context)" in validator


def test_renderer_d3d12_exports_guarded_root_signature_metadata_boundary() -> None:
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

    assert "gr_renderer_d3d12_guarded_root_signature_metadata_json" in header
    assert "renderer_d3d12_guarded_root_signature_metadata.v1" in implementation
    assert '"root_signature_ready":false' in implementation
    assert '"root_signature_serialized":false' in implementation
    assert '"root_signature_created":false' in implementation
    assert '"root_signature_version":"D3D_ROOT_SIGNATURE_VERSION_1_1"' in implementation
    assert '"root_parameter_count":0' in implementation
    assert '"descriptor_range_count":0' in implementation
    assert '"static_sampler_count":0' in implementation
    assert '"slot":"frame_constants"' in implementation
    assert '"slot":"object_constants"' in implementation
    assert '"slot":"material_constants"' in implementation
    assert '"slot":"texture_table"' in implementation
    assert '"slot":"skin_palette"' in implementation
    assert '"slot":"linear_wrap"' in implementation
    assert '"actual_root_parameters":[]' in implementation
    assert '"actual_descriptor_ranges":[]' in implementation
    assert '"descriptor_tables_ready":false' in implementation
    assert '"root_constants_ready":false' in implementation
    assert '"root_signature_from_reflection":false' in implementation
    assert '"pipeline_state_created":false' in implementation
    assert '"draw_calls_recorded":0' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert "CreateRootSignature" not in implementation
    assert "D3D12SerializeRootSignature" not in implementation
    assert "gr_renderer_d3d12_guarded_root_signature_metadata_json(context)" in validator


def test_renderer_d3d12_exports_guarded_pipeline_state_object_metadata_boundary() -> None:
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

    assert "gr_renderer_d3d12_guarded_pipeline_state_object_metadata_json" in header
    assert "renderer_d3d12_guarded_pipeline_state_object_metadata.v1" in implementation
    assert '"root_signature_ready":false' in implementation
    assert '"shader_bytecode_ready":false' in implementation
    assert '"input_layout_ready":false' in implementation
    assert '"pipeline_state_ready":false' in implementation
    assert '"pso_descriptor_ready":false' in implementation
    assert '"pipeline_state_created":false' in implementation
    assert '"field":"pRootSignature"' in implementation
    assert '"field":"VS"' in implementation
    assert '"entry":"VSMain"' in implementation
    assert '"target":"vs_6_0"' in implementation
    assert '"field":"PS"' in implementation
    assert '"entry":"PSMain"' in implementation
    assert '"target":"ps_6_0"' in implementation
    assert '"field":"InputLayout"' in implementation
    assert '"field":"BlendState"' in implementation
    assert '"field":"RasterizerState"' in implementation
    assert '"field":"DepthStencilState"' in implementation
    assert '"field":"PrimitiveTopologyType"' in implementation
    assert '"field":"RTVFormats"' in implementation
    assert '"format":"DXGI_FORMAT_R8G8B8A8_UNORM"' in implementation
    assert '"field":"DSVFormat"' in implementation
    assert '"format":"DXGI_FORMAT_D24_UNORM_S8_UINT"' in implementation
    assert '"field":"SampleDesc"' in implementation
    assert '"cached_pso_count":0' in implementation
    assert '"draw_calls_recorded":0' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert "D3D12_GRAPHICS_PIPELINE_STATE_DESC" not in implementation
    assert "CreateGraphicsPipelineState" not in implementation
    assert "gr_renderer_d3d12_guarded_pipeline_state_object_metadata_json(context)" in validator


def test_renderer_d3d12_exports_guarded_draw_command_recording_metadata_boundary() -> None:
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

    assert "gr_renderer_d3d12_guarded_draw_command_recording_metadata_json" in header
    assert "renderer_d3d12_guarded_draw_command_recording_metadata.v1" in implementation
    assert '"draw_list_ready":false' in implementation
    assert '"resource_binding_ready":false' in implementation
    assert '"root_signature_ready":false' in implementation
    assert '"pipeline_state_ready":false' in implementation
    assert '"vertex_buffers_ready":false' in implementation
    assert '"index_buffers_ready":false' in implementation
    assert '"descriptor_tables_ready":false' in implementation
    assert '"command_list_reset_for_draws":false' in implementation
    assert '"command_list_recorded_for_draws":false' in implementation
    assert '"command_list_closed_for_draws":false' in implementation
    assert '"render_targets_bound_for_draws":false' in implementation
    assert '"viewport_bound":false' in implementation
    assert '"scissor_bound":false' in implementation
    assert '"primitive_topology_bound":false' in implementation
    assert '"draw_command_count":0' in implementation
    assert '"indexed_draw_command_count":0' in implementation
    assert '"instanced_draw_command_count":0' in implementation
    assert '"skinned_draw_command_count":0' in implementation
    assert '"sprite_draw_command_count":0' in implementation
    assert '"submitted_vertex_count":0' in implementation
    assert '"submitted_index_count":0' in implementation
    assert '"submitted_instance_count":0' in implementation
    assert '"draw_packets":[]' in implementation
    assert '"present_after_draws_enabled":false' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert "DrawIndexedInstanced" not in implementation
    assert "DrawInstanced" not in implementation
    assert "gr_renderer_d3d12_guarded_draw_command_recording_metadata_json(context)" in validator


def test_renderer_d3d12_exports_guarded_draw_submission_readiness_metadata_boundary() -> None:
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

    assert "gr_renderer_d3d12_guarded_draw_submission_readiness_metadata_json" in header
    assert "renderer_d3d12_guarded_draw_submission_readiness_metadata.v1" in implementation
    assert '"draw_command_recording_ready":false' in implementation
    assert '"draw_command_list_closed":false' in implementation
    assert '"draw_submission_ready":false' in implementation
    assert '"draw_submission_attempted":false' in implementation
    assert '"command_lists_submitted_for_draws":0' in implementation
    assert '"draw_fence_created":false' in implementation
    assert '"draw_fence_signaled":false' in implementation
    assert '"draw_fence_completed":false' in implementation
    assert '"draw_fence_waited":false' in implementation
    assert '"gpu_timeline_value":0' in implementation
    assert '"cpu_wait_milliseconds":0' in implementation
    assert '"submitted_draw_call_count":0' in implementation
    assert '"submitted_triangle_count":0' in implementation
    assert '"submitted_instance_count":0' in implementation
    assert '"submitted_resource_barrier_count":0' in implementation
    assert '"present_after_draws_ready":false' in implementation
    assert '"present_after_draws_called":false' in implementation
    assert '"present_after_draws_succeeded":false' in implementation
    assert '"frame_accounting_after_draws_ready":false' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert "gr_renderer_d3d12_guarded_draw_submission_readiness_metadata_json(context)" in validator


def test_renderer_d3d12_exports_guarded_post_draw_frame_accounting_readiness_metadata_boundary() -> None:
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

    assert "gr_renderer_d3d12_guarded_post_draw_frame_accounting_readiness_metadata_json" in header
    assert "renderer_d3d12_guarded_post_draw_frame_accounting_readiness_metadata.v1" in implementation
    assert '"draw_submission_ready":false' in implementation
    assert '"draw_submission_completed":false' in implementation
    assert '"draw_fence_completed":false' in implementation
    assert '"present_after_draws_called":false' in implementation
    assert '"frame_presented_after_draws":false' in implementation
    assert '"post_draw_frame_accounting_ready":false' in implementation
    assert '"post_draw_frame_accounting_recorded":false' in implementation
    assert '"diagnostic_frame_index_after_draws":0' in implementation
    assert '"presented_frame_count_after_draws":0' in implementation
    assert '"submitted_draw_call_count":0' in implementation
    assert '"submitted_triangle_count":0' in implementation
    assert '"submitted_instance_count":0' in implementation
    assert '"submitted_vertex_count":0' in implementation
    assert '"submitted_index_count":0' in implementation
    assert '"resource_upload_count_after_draws":0' in implementation
    assert '"resource_barrier_count_after_draws":0' in implementation
    assert '"cpu_frame_time_microseconds":0' in implementation
    assert '"gpu_frame_time_microseconds":0' in implementation
    assert '"gpu_timeline_value_after_draws":0' in implementation
    assert '"frame_statistics_export_ready":false' in implementation
    assert '"draw_submission_enabled":false' in implementation
    assert (
        "gr_renderer_d3d12_guarded_post_draw_frame_accounting_readiness_metadata_json(context)"
        in validator
    )


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
        "{8225E261-C091-40A6-8386-D68B6A43FC02}",
        "{B1BC93B7-319E-4D94-95E2-91394E8D9AF9}",
        "{4CCF590C-2F20-4393-9C42-DC45FF2CD8D2}",
    }

    for guid in debug_project_guids:
        assert f"{guid}.Release|Win32.Build.0" not in solution
        assert f"{guid}.Release|x64.Build.0" not in solution
