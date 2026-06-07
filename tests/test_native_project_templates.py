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
        "{B56D386B-6E3A-48F7-A2FE-166B8D2AA730}",
    }

    for guid in debug_project_guids:
        assert f"{guid}.Release|Win32.Build.0" not in solution
        assert f"{guid}.Release|x64.Build.0" not in solution
