from __future__ import annotations

from pathlib import Path
import re
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "native" / "templates"
_PATH_READ_TEXT = Path.read_text


def _native_layout_read_text(self: Path, *args, **kwargs) -> str:
    lookup_path = self
    if not lookup_path.exists() and ROOT / "native" in lookup_path.parents:
        if lookup_path.suffix in {".h", ".hpp"}:
            public_path = lookup_path.parent / "Public" / lookup_path.name
            if public_path.exists():
                return _PATH_READ_TEXT(public_path, *args, **kwargs)
        if lookup_path.suffix == ".cpp":
            private_path = lookup_path.parent / "Private" / lookup_path.name
            if private_path.exists():
                return _PATH_READ_TEXT(private_path, *args, **kwargs)
    return _PATH_READ_TEXT(lookup_path, *args, **kwargs)


Path.read_text = _native_layout_read_text

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


def _solution_project_names(solution: str) -> list[str]:
    pattern = re.compile(
        r'Project\("\{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942\}"\) = '
        r'"([^"]+)", "[^"]+", "\{[A-F0-9-]+\}"'
    )
    return [match.group(1) for match in pattern.finditer(solution)]


def _solution_folder_names(solution: str) -> list[str]:
    pattern = re.compile(
        r'Project\("\{2150E333-8FDC-42A3-9474-1A3956D46DE8\}"\) = '
        r'"([^"]+)", "[^"]+", "\{[A-F0-9-]+\}"'
    )
    return [match.group(1) for match in pattern.finditer(solution)]


def _manifest_rows() -> list[tuple[str, str, str]]:
    manifest = (ROOT / "knowledge_base" / "native_project_namespace_manifest.md").read_text(
        encoding="utf-8"
    )
    rows: list[tuple[str, str, str]] = []
    for line in manifest.splitlines():
        if not line.startswith("| `GhostRigger."):
            continue
        columns = [column.strip() for column in line.strip("|").split("|")]
        if len(columns) < 7:
            continue
        old_name = columns[0].strip("`")
        new_name = columns[1].strip("`")
        status = columns[6]
        rows.append((old_name, new_name, status))
    return rows


def test_native_vcxproj_templates_parse_after_token_substitution() -> None:
    for template in TEMPLATE_DIR.glob("*.vcxproj.template"):
        rendered = _render_template(template)
        assert "{{" not in rendered
        ET.fromstring(rendered)


def test_native_template_readme_names_required_phase_one_metadata() -> None:
    readme = (TEMPLATE_DIR / "README.md").read_text(encoding="utf-8")

    assert "GhostRigger.Native.Core.Host" in readme
    assert "GhostRigger.Native.Core.Foundation" in readme
    assert "GhostRigger.Native.Core.Diagnostics" in (ROOT / "native" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "GhostRigger.Native.Core.Math" in (ROOT / "native" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "GhostRigger.Runtime.Core.Host" in readme
    assert "GhostRigger.Native.Core.Foundation.{System}" in readme
    assert "GhostRigger.Runtime.Shared.{System}" in readme
    assert "GhostRigger.Core.Tools.{Toolname}" in readme
    assert "GhostRigger.Core.GUI.Display.*" in readme
    assert "GhostRigger.Core.GUI.Helpers.*" in readme
    assert "knowledge_base/package_ownership_model.md" in readme
    assert "GhostRigger.Runtime.Shared.Descriptors" in (ROOT / "native" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "GhostRigger.Runtime.Shared.Resources" in (ROOT / "native" / "README.md").read_text(
        encoding="utf-8"
    )
    native_readme = (ROOT / "native" / "README.md").read_text(encoding="utf-8")
    assert "GhostRigger.Core.Rendering.Backends.D3D12" in native_readme
    assert "GhostRigger.Core.Rendering.Backends.Null" in native_readme
    assert "GhostRigger.Core.Rendering.*" in native_readme
    assert "current canonical native" in native_readme
    assert "renderer contract/backend package names" in native_readme
    assert "Owner surface" in readme
    assert "Owner package" in readme
    assert "Bridge method" in readme
    assert "Owner: LordVaderCW" in readme
    assert "Intersects:" in readme


def test_native_solution_keeps_real_projects_without_solution_folders() -> None:
    solution = (ROOT / "GhostRigger.sln").read_text(encoding="utf-8")
    assert len(_solution_project_names(solution)) == 92
    assert _solution_folder_names(solution) == []
    assert "GlobalSection(NestedProjects)" not in solution


def test_native_namespace_manifest_covers_solution_projects() -> None:
    solution = (ROOT / "GhostRigger.sln").read_text(encoding="utf-8")
    solution_names = set(_solution_project_names(solution))
    rows = _manifest_rows()
    manifest = {old_name: new_name for old_name, new_name, _status in rows}
    expected_solution_names = {
        new_name if "renamed in" in status else old_name
        for old_name, new_name, status in rows
    }

    assert len(manifest) == 94
    assert expected_solution_names == solution_names
    assert manifest["GhostRigger.Native"] == "GhostRigger.Native.Core.Host"
    assert manifest["GhostRigger.Native.Core.Foundation"] == "GhostRigger.Native.Core.Foundation"
    assert (
        manifest["GhostRigger.Native.Core.Diagnostics"]
        == "GhostRigger.Native.Core.Diagnostics"
    )
    assert manifest["GhostRigger.Native.Core.Math"] == "GhostRigger.Native.Core.Math"
    assert manifest["GhostRigger.Skeleton"] == "GhostRigger.Core.Scene.Skeleton"
    assert manifest["GhostRigger.Core.Tools.SequenceEditor"] == "GhostRigger.Core.Tools.SequenceEditor"
    assert (
        manifest["GhostRigger.Tools.NodesSkeletonBrowser"]
        == "GhostRigger.Core.Tools.NodeSkeletonBrowser"
    )
    assert "GhostRigger.Selection" not in solution_names


def test_native_docs_define_canonical_package_ownership_model() -> None:
    docs = "\n".join(
        [
            (ROOT / "AGENTS.md").read_text(encoding="utf-8"),
            (ROOT / "native" / "README.md").read_text(encoding="utf-8"),
            (ROOT / "knowledge_base" / "cpp_integration_phases.md").read_text(encoding="utf-8"),
            (ROOT / "knowledge_base" / "native_migration_plan.md").read_text(encoding="utf-8"),
            (ROOT / "knowledge_base" / "package_ownership_model.md").read_text(encoding="utf-8"),
        ]
    )

    assert "GhostRigger.Core.Tools.{Toolname}" in docs
    assert "GhostRigger.Core.Tools.Retargeting" in docs
    assert "GhostRigger.Core.GUI.Display.*" in docs
    assert "GhostRigger.Core.GUI.Helpers.*" in docs
    assert "GhostRigger.Core.Rendering.Backends.{Backend}" in docs
    assert "GhostRigger.Core.IO.*" in docs
    assert "GhostRigger.Core.Automation.*" in docs
    assert "GhostRigger.Core.Resources.*" in docs
    assert "GhostRigger.Core.Formats.*" in docs
    assert "GhostRigger.Adapters.*" in docs
    assert "legacy" in docs


def test_native_toolbox_window_migration_candidates_define_first_phase_one_surfaces() -> None:
    candidates = (
        ROOT / "knowledge_base" / "native_toolbox_window_migration_candidates.md"
    ).read_text(encoding="utf-8")

    assert "GhostRigger.Core.Tools.Retargeting" in candidates
    assert "GhostRigger.Core.Tools.Export" in candidates
    assert "GhostRigger.Core.Tools.CharacterBuilder" in candidates
    assert "GhostRigger.Core.GUI.Display.Shell.Main" in candidates
    assert "GhostRigger.Core.GUI.Display.*" in candidates
    assert "GhostRigger.Core.GUI.Helpers.*" in candidates
    assert "Canonical target owner" in candidates
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
        / "GhostRigger.Core.Tools.Retargeting"
        / "GhostRigger.Core.Tools.Retargeting.vcxproj"
    ).read_text(encoding="utf-8")
    readme = (
        ROOT
        / "native"
        / "GhostRigger.Core.Tools.Retargeting"
        / "README.md"
    ).read_text(encoding="utf-8")

    assert "GhostRigger.Core.Tools.Retargeting" in solution
    assert "GhostRigger.Core.Tools.Retargeting.DEBUG" not in solution
    assert "<TargetName>GhostRigger.Core.Tools.Retargeting</TargetName>" in project
    assert "GHOSTRIGGER_TOOLS_RETARGETING_EXPORTS" in project
    assert "Owner surface: Retarget Workbench" in readme
    assert "Bridge method: C ABI DLL" in readme


def test_tools_retargeting_exports_diagnostic_c_abi_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Tools.Retargeting"
        / "GhostRiggerToolsRetargeting.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Tools.Retargeting"
        / "GhostRiggerToolsRetargeting.cpp"
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


def test_tools_export_project_scaffold_matches_phase_one_boundary() -> None:
    solution = (ROOT / "GhostRigger.sln").read_text(encoding="utf-8")
    project = (
        ROOT
        / "native"
        / "GhostRigger.Core.Tools.Export"
        / "GhostRigger.Core.Tools.Export.vcxproj"
    ).read_text(encoding="utf-8")
    readme = (
        ROOT
        / "native"
        / "GhostRigger.Core.Tools.Export"
        / "README.md"
    ).read_text(encoding="utf-8")

    assert "GhostRigger.Core.Tools.Export" in solution
    assert "GhostRigger.Core.Tools.Export.DEBUG" not in solution
    assert "<TargetName>GhostRigger.Core.Tools.Export</TargetName>" in project
    assert "GHOSTRIGGER_TOOLS_EXPORT_EXPORTS" in project
    assert "Owner surface: Export and validation workflow" in readme
    assert "Bridge method: C ABI DLL" in readme


def test_tools_export_exports_diagnostic_c_abi_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Tools.Export"
        / "GhostRiggerToolsExport.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Tools.Export"
        / "GhostRiggerToolsExport.cpp"
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


def test_tools_character_builder_project_scaffold_matches_phase_one_boundary() -> None:
    solution = (ROOT / "GhostRigger.sln").read_text(encoding="utf-8")
    project = (
        ROOT
        / "native"
        / "GhostRigger.Core.Tools.CharacterBuilder"
        / "GhostRigger.Core.Tools.CharacterBuilder.vcxproj"
    ).read_text(encoding="utf-8")
    readme = (
        ROOT
        / "native"
        / "GhostRigger.Core.Tools.CharacterBuilder"
        / "README.md"
    ).read_text(encoding="utf-8")

    assert "GhostRigger.Core.Tools.CharacterBuilder" in solution
    assert "GhostRigger.Core.Tools.CharacterBuilder.DEBUG" not in solution
    assert "<TargetName>GhostRigger.Core.Tools.CharacterBuilder</TargetName>" in project
    assert "GHOSTRIGGER_TOOLS_CHARACTER_BUILDER_EXPORTS" in project
    assert "Owner surface: Character Studio" in readme
    assert "Bridge method: C ABI DLL" in readme


def test_tools_character_builder_exports_diagnostic_c_abi_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Tools.CharacterBuilder"
        / "GhostRiggerToolsCharacterBuilder.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Tools.CharacterBuilder"
        / "GhostRiggerToolsCharacterBuilder.cpp"
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


def test_windows_main_window_project_scaffold_matches_phase_one_boundary() -> None:
    solution = (ROOT / "GhostRigger.sln").read_text(encoding="utf-8")
    project = (
        ROOT
        / "native"
        / "GhostRigger.Core.GUI.Display.Shell.Main"
        / "GhostRigger.Core.GUI.Display.Shell.Main.vcxproj"
    ).read_text(encoding="utf-8")
    readme = (
        ROOT
        / "native"
        / "GhostRigger.Core.GUI.Display.Shell.Main"
        / "README.md"
    ).read_text(encoding="utf-8")

    assert "GhostRigger.Core.GUI.Display.Shell.Main" in solution
    assert "GhostRigger.Core.GUI.Display.Shell.Main.DEBUG" not in solution
    assert "<TargetName>GhostRigger.Core.GUI.Display.Shell.Main</TargetName>" in project
    assert "GHOSTRIGGER_WINDOWS_MAIN_WINDOW_EXPORTS" in project
    assert "Owner surface: Main window composition shell" in readme
    assert "Bridge method: C ABI DLL" in readme


def test_native_host_executable_owns_splash_resources_without_a_second_exe() -> None:
    solution = (ROOT / "GhostRigger.sln").read_text(encoding="utf-8")
    project_dir = ROOT / "native" / "GhostRigger.Native.Core.Host"
    project = (project_dir / "GhostRigger.Native.Core.Host.vcxproj").read_text(encoding="utf-8")
    filters = (project_dir / "GhostRigger.Native.Core.Host.vcxproj.filters").read_text(encoding="utf-8")
    rc = (project_dir / "GhostRiggerNativeSplash.rc").read_text(encoding="utf-8")
    header = (project_dir / "Public" / "GhostRiggerNativeSplashResource.h").read_text(encoding="utf-8")

    assert "GhostRigger.Core.GUI.Display.Shell.Main.Splash" not in solution
    assert "<TargetName>GhostRigger</TargetName>" in project
    assert "<ResourceCompile Include=\"GhostRiggerNativeSplash.rc\" />" in project
    assert "QtInstallDir" not in project
    assert "Qt6Widgets.lib" not in project
    assert "GhostRigger.Core.GUI.Display.Shell.Main.Splash.vcxproj" not in project
    assert "Private\\GhostRiggerWindowsSplash.cpp" not in project
    assert "IDR_NATIVE_SPLASH_LOGO" in header
    assert "assets/icons/ghostrigger_1024x1024.png" in rc
    assert "Resources\\icons" in filters
    assert "Resources\\svg" in filters
    assert "IDR_NATIVE_SPLASH_LOGO RCDATA" in rc
    assert not (ROOT / "native" / "GhostRigger.Core.GUI.Display.Shell.Main.Splash" / "GhostRigger.Core.GUI.Display.Shell.Main.Splash.vcxproj").exists()


def test_windows_main_window_exports_diagnostic_c_abi_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.GUI.Display.Shell.Main"
        / "GhostRiggerWindowsMainWindow.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.GUI.Display.Shell.Main"
        / "GhostRiggerWindowsMainWindow.cpp"
    ).read_text(encoding="utf-8")

    assert "gr_windows_main_window_version" in header
    assert "gr_windows_main_window_capabilities_json" in header
    assert "gr_windows_main_window_owner_boundary_json" in header
    assert "gr_windows_main_window_host_service_schema_json" in header
    assert '"window_package":true' in implementation
    assert '"owner_surface":"Main window composition shell"' in implementation
    assert '"bridge_method":"C ABI DLL"' in implementation
    assert '"native_shell_enabled":false' in implementation
    assert '"python_fallback_required":true' in implementation
    assert "windows_main_window_owner_boundary.v1" in implementation
    assert "windows_main_window_host_service_schema.v1" in implementation
    assert '"host_module_registered":false' in implementation
    assert '"visible_shell_mutation_allowed":false' in implementation


def test_extra_window_project_scaffolds_match_phase_one_boundaries() -> None:
    solution = (ROOT / "GhostRigger.sln").read_text(encoding="utf-8")
    cases = (
        (
            "GhostRigger.Core.Tools.ModuleEditor",
            "GHOSTRIGGER_WINDOWS_LEVEL_EDITOR_EXPORTS",
            "GhostRiggerWindowsLevelEditor.h",
            "GhostRiggerWindowsLevelEditor.cpp",
            "GhostRiggerWindowsLevelEditorDEBUG.cpp",
            "Level Editor",
            "windows_level_editor_owner_boundary.v1",
            "windows_level_editor_host_service_schema.v1",
        ),
        (
            "GhostRigger.Core.Tools.Retargeting.Workbench",
            "GHOSTRIGGER_WINDOWS_ANIMATION_RETARGET_WORKBENCH_EXPORTS",
            "GhostRiggerWindowsAnimationRetargetWorkbench.h",
            "GhostRiggerWindowsAnimationRetargetWorkbench.cpp",
            "GhostRiggerWindowsAnimationRetargetWorkbenchDEBUG.cpp",
            "Animation Retarget Workbench",
            "windows_animation_retarget_workbench_owner_boundary.v1",
            "windows_animation_retarget_workbench_host_service_schema.v1",
        ),
        (
            "GhostRigger.Core.Tools.Rigging",
            "GHOSTRIGGER_WINDOWS_LEGACY_RIGGING_WINDOW_EXPORTS",
            "GhostRiggerWindowsLegacyRiggingWindow.h",
            "GhostRiggerWindowsLegacyRiggingWindow.cpp",
            "GhostRiggerWindowsLegacyRiggingWindowDEBUG.cpp",
            "Legacy Rigging Window",
            "windows_legacy_rigging_window_owner_boundary.v1",
            "windows_legacy_rigging_window_host_service_schema.v1",
        ),
        (
            "GhostRigger.Core.Tools.UnrealAnimator",
            "GHOSTRIGGER_WINDOWS_UNREAL_ANIMATOR_WINDOW_EXPORTS",
            "GhostRiggerWindowsUnrealAnimatorWindow.h",
            "GhostRiggerWindowsUnrealAnimatorWindow.cpp",
            "GhostRiggerWindowsUnrealAnimatorWindowDEBUG.cpp",
            "Unreal Animator Window",
            "windows_unreal_animator_window_owner_boundary.v1",
            "windows_unreal_animator_window_host_service_schema.v1",
        ),
    )

    for (
        project_name,
        export_define,
        header_name,
        implementation_name,
        validator_name,
        owner,
        owner_schema,
        host_schema,
    ) in cases:
        project_dir = ROOT / "native" / project_name
        debug_dir = ROOT / "native" / f"{project_name}.DEBUG"
        project = (project_dir / f"{project_name}.vcxproj").read_text(encoding="utf-8")
        readme = (project_dir / "README.md").read_text(encoding="utf-8")
        header = (project_dir / header_name).read_text(encoding="utf-8")
        implementation = (project_dir / implementation_name).read_text(encoding="utf-8")

        assert project_name in solution
        assert f"{project_name}.DEBUG" not in solution
        assert f"<TargetName>{project_name}</TargetName>" in project
        assert export_define in project
        assert f"Owner surface: {owner}" in readme
        assert "Bridge method: C ABI DLL" in readme
        assert "_version" in header
        assert "_capabilities_json" in header
        assert "_owner_boundary_json" in header
        assert "_host_service_schema_json" in header
        assert '"window_package":true' in implementation
        assert f'"owner_surface":"{owner}"' in implementation
        assert '"native_shell_enabled":false' in implementation
        assert '"python_fallback_required":true' in implementation
        assert owner_schema in implementation
        assert host_schema in implementation


def test_browser_tool_project_scaffolds_match_phase_one_boundaries() -> None:
    solution = (ROOT / "GhostRigger.sln").read_text(encoding="utf-8")
    cases = (
        (
            "GhostRigger.Core.Tools.ContentBrowser",
            "GHOSTRIGGER_TOOLS_CONTENT_BROWSER_EXPORTS",
            "GhostRiggerToolsContentBrowser.h",
            "GhostRiggerToolsContentBrowser.cpp",
            "GhostRiggerToolsContentBrowserDEBUG.cpp",
            "Content Browser",
            "catalogue_schema",
        ),
        (
            "GhostRigger.Core.Tools.ResourceBrowser",
            "GHOSTRIGGER_TOOLS_RESOURCE_BROWSER_EXPORTS",
            "GhostRiggerToolsResourceBrowser.h",
            "GhostRiggerToolsResourceBrowser.cpp",
            "GhostRiggerToolsResourceBrowserDEBUG.cpp",
            "Resource Browser",
            "catalogue_schema",
        ),
        (
            "GhostRigger.Core.Tools.TwoDABrowser",
            "GHOSTRIGGER_TOOLS_TWO_DA_BROWSER_EXPORTS",
            "GhostRiggerToolsTwoDABrowser.h",
            "GhostRiggerToolsTwoDABrowser.cpp",
            "GhostRiggerToolsTwoDABrowserDEBUG.cpp",
            "2DA Browser",
            "table_schema",
        ),
    )

    for project_name, export_define, header_name, implementation_name, validator_name, owner, schema in cases:
        project_dir = ROOT / "native" / project_name
        debug_dir = ROOT / "native" / f"{project_name}.DEBUG"
        project = (project_dir / f"{project_name}.vcxproj").read_text(encoding="utf-8")
        readme = (project_dir / "README.md").read_text(encoding="utf-8")
        header = (project_dir / header_name).read_text(encoding="utf-8")
        implementation = (project_dir / implementation_name).read_text(encoding="utf-8")

        assert project_name in solution
        assert f"{project_name}.DEBUG" not in solution
        assert f"<TargetName>{project_name}</TargetName>" in project
        assert export_define in project
        assert f"Owner surface: {owner}" in readme
        assert "Bridge method: C ABI DLL" in readme
        assert "_version" in header
        assert "_capabilities_json" in header
        assert '"tool_package":true' in implementation
        assert f'"owner_surface":"{owner}"' in implementation
        assert '"python_fallback_required":true' in implementation
        assert schema in implementation


def test_scene_workbench_tool_project_scaffolds_match_phase_one_boundaries() -> None:
    solution = (ROOT / "GhostRigger.sln").read_text(encoding="utf-8")
    cases = (
        (
            "GhostRigger.Core.Tools.SceneInformation",
            "GHOSTRIGGER_TOOLS_SCENE_INFORMATION_EXPORTS",
            "GhostRiggerToolsSceneInformation.h",
            "GhostRiggerToolsSceneInformation.cpp",
            "GhostRiggerToolsSceneInformationDEBUG.cpp",
            "Scene Information",
            "scene_summary_schema",
            "native_scene_query_enabled",
        ),
        (
            "GhostRigger.Core.Tools.Properties",
            "GHOSTRIGGER_TOOLS_PROPERTIES_EXPORTS",
            "GhostRiggerToolsProperties.h",
            "GhostRiggerToolsProperties.cpp",
            "GhostRiggerToolsPropertiesDEBUG.cpp",
            "Properties",
            "property_packet_schema",
            "native_property_edit_enabled",
        ),
        (
            "GhostRigger.Core.Tools.Lighting",
            "GHOSTRIGGER_TOOLS_LIGHTING_EXPORTS",
            "GhostRiggerToolsLighting.h",
            "GhostRiggerToolsLighting.cpp",
            "GhostRiggerToolsLightingDEBUG.cpp",
            "Lighting",
            "light_packet_schema",
            "native_light_eval_enabled",
        ),
        (
            "GhostRigger.Core.Tools.Camera",
            "GHOSTRIGGER_TOOLS_CAMERA_EXPORTS",
            "GhostRiggerToolsCamera.h",
            "GhostRiggerToolsCamera.cpp",
            "GhostRiggerToolsCameraDEBUG.cpp",
            "Camera",
            "camera_packet_schema",
            "native_camera_eval_enabled",
        ),
        (
            "GhostRigger.Core.Tools.ModuleMeshes",
            "GHOSTRIGGER_TOOLS_MODULE_MESHES_EXPORTS",
            "GhostRiggerToolsModuleMeshes.h",
            "GhostRiggerToolsModuleMeshes.cpp",
            "GhostRiggerToolsModuleMeshesDEBUG.cpp",
            "Module Meshes",
            "mesh_packet_schema",
            "native_mesh_index_enabled",
        ),
    )

    for (
        project_name,
        export_define,
        header_name,
        implementation_name,
        validator_name,
        owner,
        schema,
        disabled_flag,
    ) in cases:
        project_dir = ROOT / "native" / project_name
        debug_dir = ROOT / "native" / f"{project_name}.DEBUG"
        project = (project_dir / f"{project_name}.vcxproj").read_text(encoding="utf-8")
        readme = (project_dir / "README.md").read_text(encoding="utf-8")
        header = (project_dir / header_name).read_text(encoding="utf-8")
        implementation = (project_dir / implementation_name).read_text(encoding="utf-8")

        assert project_name in solution
        assert f"{project_name}.DEBUG" not in solution
        assert f"<TargetName>{project_name}</TargetName>" in project
        assert export_define in project
        assert f"Owner surface: {owner}" in readme
        assert "Bridge method: C ABI DLL" in readme
        assert "_version" in header
        assert "_capabilities_json" in header
        assert '"tool_package":true' in implementation
        assert f'"owner_surface":"{owner}"' in implementation
        assert f'"{disabled_flag}":false' in implementation
        assert '"python_fallback_required":true' in implementation
        assert schema in implementation


def test_final_phase_one_tool_project_scaffolds_match_phase_one_boundaries() -> None:
    solution = (ROOT / "GhostRigger.sln").read_text(encoding="utf-8")
    cases = (
        (
            "GhostRigger.Core.Tools.BAS",
            "GhostRigger.Core.Tools.BAS",
            "GHOSTRIGGER_TOOLS_BODY_ATTACHMENT_SYSTEM_EXPORTS",
            "GhostRiggerToolsBodyAttachmentSystem.h",
            "GhostRiggerToolsBodyAttachmentSystem.cpp",
            "GhostRiggerToolsBodyAttachmentSystemDEBUG.cpp",
            "Body Attachment System",
            "attachment_packet_schema",
            "native_attachment_eval_enabled",
        ),
        (
            "GhostRigger.Core.Tools.NodeSkeletonBrowser",
            "GhostRigger.Core.Tools.NodeSkeletonBrowser",
            "GHOSTRIGGER_TOOLS_NODES_SKELETON_BROWSER_EXPORTS",
            "GhostRiggerToolsNodesSkeletonBrowser.h",
            "GhostRiggerToolsNodesSkeletonBrowser.cpp",
            "GhostRiggerToolsNodesSkeletonBrowserDEBUG.cpp",
            "Nodes/Skeleton Browser",
            "node_tree_schema",
            "native_node_tree_query_enabled",
        ),
        (
            "GhostRigger.Core.Tools.SpriteMaterials",
            "GhostRigger.Core.Tools.SpriteMaterials",
            "GHOSTRIGGER_TOOLS_SPRITE_MATERIALS_EXPORTS",
            "GhostRiggerToolsSpriteMaterials.h",
            "GhostRiggerToolsSpriteMaterials.cpp",
            "GhostRiggerToolsSpriteMaterialsDEBUG.cpp",
            "Sprite Materials",
            "material_packet_schema",
            "native_sprite_material_eval_enabled",
        ),
        (
            "GhostRigger.Core.Tools.PivotControls",
            "GhostRigger.Core.Tools.PivotControls",
            "GHOSTRIGGER_TOOLS_PIVOT_CONTROLS_EXPORTS",
            "GhostRiggerToolsPivotControls.h",
            "GhostRiggerToolsPivotControls.cpp",
            "GhostRiggerToolsPivotControlsDEBUG.cpp",
            "PivotControls",
            "pivot_packet_schema",
            "native_pivot_edit_enabled",
        ),
        (
            "GhostRigger.Core.Tools.SequenceEditor",
            "GhostRigger.Core.Tools.SequenceEditor",
            "GHOSTRIGGER_TOOLS_SEQUENCE_EDITOR_EXPORTS",
            "GhostRiggerToolsSequenceEditor.h",
            "GhostRiggerToolsSequenceEditor.cpp",
            "GhostRiggerToolsSequenceEditorDEBUG.cpp",
            "Sequence Editor",
            "sequence_packet_schema",
            "native_sequence_eval_enabled",
        ),
    )

    for (
        project_name,
        solution_name,
        export_define,
        header_name,
        implementation_name,
        validator_name,
        owner,
        schema,
        disabled_flag,
    ) in cases:
        project_dir = ROOT / "native" / project_name
        debug_dir = ROOT / "native" / f"{project_name}.DEBUG"
        project = (project_dir / f"{project_name}.vcxproj").read_text(encoding="utf-8")
        readme = (project_dir / "README.md").read_text(encoding="utf-8")
        header = (project_dir / header_name).read_text(encoding="utf-8")
        implementation = (project_dir / implementation_name).read_text(encoding="utf-8")

        assert solution_name in solution
        assert f"{project_name}.DEBUG" not in solution
        assert f"<TargetName>{solution_name}</TargetName>" in project
        assert export_define in project
        assert f"Owner surface: {owner}" in readme
        assert "Bridge method: C ABI DLL" in readme
        assert "_version" in header
        assert "_capabilities_json" in header
        assert '"tool_package":true' in implementation
        assert f'"owner_surface":"{owner}"' in implementation
        assert f'"{disabled_flag}":false' in implementation
        assert '"python_fallback_required":true' in implementation
        assert schema in implementation


def test_native_dll_template_keeps_release_output_shippable_only() -> None:
    template = (TEMPLATE_DIR / "native_dll.vcxproj.template").read_text(encoding="utf-8")

    assert "<GenerateDebugInformation>false</GenerateDebugInformation>" in template
    assert "$(TargetDir)$(TargetName).pdb" in template
    assert "$(TargetDir)$(TargetName).exp" in template


def test_native_template_readme_documents_release_output_rule() -> None:
    readme = (TEMPLATE_DIR / "README.md").read_text(encoding="utf-8")

    assert "Release output contains only `.exe`, `.dll`, and `.lib` files" in readme
    assert "`.DEBUG` application projects must not be added to the solution" in readme


def test_native_host_project_emits_product_executable_name() -> None:
    project_path = ROOT / "native" / "GhostRigger.Native.Core.Host" / "GhostRigger.Native.Core.Host.vcxproj"
    tree = ET.parse(project_path)
    ns = {"msb": "http://schemas.microsoft.com/developer/msbuild/2003"}

    target_names = [node.text for node in tree.findall(".//msb:TargetName", ns)]

    assert target_names == ["GhostRigger"]


def test_native_host_embedded_program_name_matches_product_executable() -> None:
    main_cpp = (ROOT / "native" / "GhostRigger.Native.Core.Host" / "main.cpp").read_text(encoding="utf-8")

    assert 'L"GhostRigger.exe"' in main_cpp
    assert 'L"GhostRigger.Native.exe"' not in main_cpp
    assert 'executable_directory().value_or(repo_root) / L"main.py"' in main_cpp
    assert 'repo_root / L"main.py"' not in main_cpp


def test_native_host_project_owns_and_copies_its_entrypoint() -> None:
    project_path = ROOT / "native" / "GhostRigger.Native.Core.Host" / "GhostRigger.Native.Core.Host.vcxproj"
    project = project_path.read_text(encoding="utf-8")
    host_main = ROOT / "native" / "GhostRigger.Native.Core.Host" / "main.py"

    assert host_main.exists()
    assert '<None Include="main.py" />' in project
    assert '<None Include="..\\..\\main.py" />' not in project
    assert 'copy /Y "$(ProjectDir)main.py" "$(OutDir)main.py"' in project


def test_native_host_python_entrypoint_is_not_root_main_wrapper() -> None:
    host_main = (ROOT / "native" / "GhostRigger.Native.Core.Host" / "main.py").read_text(encoding="utf-8")

    assert "import main" not in host_main
    assert "runpy.run_path" not in host_main
    assert "GhostRigger Native Host starting" in host_main
    assert "from src.gui.qt_lib.windows.qt_main_window import run as run_qt" in host_main


def test_native_host_marks_visual_studio_runtime_provenance() -> None:
    main_cpp = (ROOT / "native" / "GhostRigger.Native.Core.Host" / "main.cpp").read_text(encoding="utf-8")

    assert 'SetEnvironmentVariableW(L"GHOSTRIGGER_NATIVE_HOST", L"1")' in main_cpp
    assert 'SetEnvironmentVariableW(L"GHOSTRIGGER_EMBEDDED_PYTHON", L"1")' in main_cpp
    assert 'GHOSTRIGGER_NATIVE_REPO_ROOT' in main_cpp
    assert 'GHOSTRIGGER_NATIVE_BUILD_OUTPUT_DIR' in main_cpp
    assert 'GHOSTRIGGER_NATIVE_PYTHON_ENTRYPOINT' in main_cpp
    assert 'GHOSTRIGGER_NATIVE_PAYLOAD_AUDIT_REQUIRED' in main_cpp
    assert "log_native_dependency_audit_to_console(*exe_dir)" in main_cpp


def test_native_core_diagnostics_project_uses_phase_one_naming_and_release_hygiene() -> None:
    project_path = (
        ROOT
        / "native"
        / "GhostRigger.Native.Core.Diagnostics"
        / "GhostRigger.Native.Core.Diagnostics.vcxproj"
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

    assert target_names == ["GhostRigger.Native.Core.Diagnostics"]
    assert any("GhostRigger.Native.Core.Foundation.vcxproj" in ref for ref in project_refs)
    assert [node.text for node in release_debug_info] == ["false"]
    assert any("$(TargetDir)$(TargetName).pdb" in command for command in post_build_commands)
    assert any("$(TargetDir)$(TargetName).exp" in command for command in post_build_commands)


def test_native_core_math_project_uses_phase_one_naming_and_release_hygiene() -> None:
    project_path = (
        ROOT
        / "native"
        / "GhostRigger.Native.Core.Math"
        / "GhostRigger.Native.Core.Math.vcxproj"
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

    assert target_names == ["GhostRigger.Native.Core.Math"]
    assert any("GhostRigger.Native.Core.Foundation.vcxproj" in ref for ref in project_refs)
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
    assert any("GhostRigger.Native.Core.Foundation.vcxproj" in ref for ref in project_refs)
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
    assert any("GhostRigger.Native.Core.Foundation.vcxproj" in ref for ref in project_refs)
    assert [node.text for node in release_debug_info] == ["false"]
    assert any("$(TargetDir)$(TargetName).pdb" in command for command in post_build_commands)
    assert any("$(TargetDir)$(TargetName).exp" in command for command in post_build_commands)


def test_renderer_contracts_project_uses_phase_one_naming_and_release_hygiene() -> None:
    project_path = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Contracts"
        / "GhostRigger.Core.Rendering.Contracts.vcxproj"
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

    assert target_names == ["GhostRigger.Core.Rendering.Contracts"]
    assert any("GhostRigger.Native.Core.Foundation.vcxproj" in ref for ref in project_refs)
    assert [node.text for node in release_debug_info] == ["false"]
    assert any("$(TargetDir)$(TargetName).pdb" in command for command in post_build_commands)
    assert any("$(TargetDir)$(TargetName).exp" in command for command in post_build_commands)


def test_renderer_null_project_uses_phase_one_naming_and_release_hygiene() -> None:
    project_path = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.Null"
        / "GhostRigger.Core.Rendering.Backends.Null.vcxproj"
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

    assert target_names == ["GhostRigger.Core.Rendering.Backends.Null"]
    assert any("GhostRigger.Core.Rendering.Contracts.vcxproj" in ref for ref in project_refs)
    assert [node.text for node in release_debug_info] == ["false"]
    assert any("$(TargetDir)$(TargetName).pdb" in command for command in post_build_commands)
    assert any("$(TargetDir)$(TargetName).exp" in command for command in post_build_commands)


def test_renderer_d3d12_project_uses_phase_one_naming_and_release_hygiene() -> None:
    project_path = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRigger.Core.Rendering.Backends.D3D12.vcxproj"
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

    assert target_names == ["GhostRigger.Core.Rendering.Backends.D3D12"]
    assert any("GhostRigger.Core.Rendering.Contracts.vcxproj" in ref for ref in project_refs)
    assert [node.text for node in release_debug_info] == ["false"]
    assert any("d3d12.lib" in dependencies for dependencies in link_dependencies)
    assert any("dxgi.lib" in dependencies for dependencies in link_dependencies)
    assert any("$(TargetDir)$(TargetName).pdb" in command for command in post_build_commands)
    assert any("$(TargetDir)$(TargetName).exp" in command for command in post_build_commands)


def test_renderer_moderngl_project_uses_phase_one_naming_and_release_hygiene() -> None:
    project_path = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.ModernGL"
        / "GhostRigger.Core.Rendering.Backends.ModernGL.vcxproj"
    )
    tree = ET.parse(project_path)
    ns = {"msb": "http://schemas.microsoft.com/developer/msbuild/2003"}

    target_names = [node.text for node in tree.findall(".//msb:TargetName", ns)]
    project_refs = [node.attrib["Include"] for node in tree.findall(".//msb:ProjectReference", ns)]
    release_debug_info = tree.findall(
        ".//msb:ItemDefinitionGroup[@Condition=\"'$(Configuration)'=='Release'\""
        "]/msb:Link/msb:GenerateDebugInformation",
        ns,
    )
    post_build_commands = [
        node.text or ""
        for node in tree.findall(
            ".//msb:ItemDefinitionGroup[@Condition=\"'$(Configuration)'=='Release'\""
            "]/msb:PostBuildEvent/msb:Command",
            ns,
        )
    ]

    assert target_names == ["GhostRigger.Core.Rendering.Backends.ModernGL"]
    assert any("GhostRigger.Core.Rendering.Contracts.vcxproj" in ref for ref in project_refs)
    assert [node.text for node in release_debug_info] == ["false"]
    assert any("$(TargetDir)$(TargetName).pdb" in command for command in post_build_commands)
    assert any("$(TargetDir)$(TargetName).exp" in command for command in post_build_commands)


def test_renderer_pygfx_project_uses_phase_one_naming_and_release_hygiene() -> None:
    project_path = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.PyGFX"
        / "GhostRigger.Core.Rendering.Backends.PyGFX.vcxproj"
    )
    tree = ET.parse(project_path)
    ns = {"msb": "http://schemas.microsoft.com/developer/msbuild/2003"}

    target_names = [node.text for node in tree.findall(".//msb:TargetName", ns)]
    project_refs = [node.attrib["Include"] for node in tree.findall(".//msb:ProjectReference", ns)]
    release_debug_info = tree.findall(
        ".//msb:ItemDefinitionGroup[@Condition=\"'$(Configuration)'=='Release'\""
        "]/msb:Link/msb:GenerateDebugInformation",
        ns,
    )
    post_build_commands = [
        node.text or ""
        for node in tree.findall(
            ".//msb:ItemDefinitionGroup[@Condition=\"'$(Configuration)'=='Release'\""
            "]/msb:PostBuildEvent/msb:Command",
            ns,
        )
    ]

    assert target_names == ["GhostRigger.Core.Rendering.Backends.PyGFX"]
    assert any("GhostRigger.Core.Rendering.Contracts.vcxproj" in ref for ref in project_refs)
    assert [node.text for node in release_debug_info] == ["false"]
    assert any("$(TargetDir)$(TargetName).pdb" in command for command in post_build_commands)
    assert any("$(TargetDir)$(TargetName).exp" in command for command in post_build_commands)


def test_renderer_moderngl_exports_diagnostic_bridge_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.ModernGL"
        / "GhostRiggerRendererModernGL.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.ModernGL"
        / "GhostRiggerRendererModernGL.cpp"
    ).read_text(encoding="utf-8")
    assert "gr_renderer_moderngl_version" in header
    assert "gr_renderer_moderngl_capabilities_json" in header
    assert "gr_renderer_moderngl_backend_info_json" in header
    assert "gr_renderer_moderngl_adapter_bridge_json" in header
    assert "gr_renderer_moderngl_frame_diagnostics_json" in header
    assert '"renderer_backend":true' in implementation
    assert '"backend":"moderngl"' in implementation
    assert '"python_adapter_required":true' in implementation
    assert '"native_device_owner":false' in implementation
    assert '"diagnostic_contracts":["frame_diagnostics"]' in implementation
    assert '"fallback_backend":"python_moderngl"' in implementation


def test_renderer_pygfx_exports_diagnostic_bridge_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.PyGFX"
        / "GhostRiggerRendererPyGFX.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.PyGFX"
        / "GhostRiggerRendererPyGFX.cpp"
    ).read_text(encoding="utf-8")

    assert "gr_renderer_pygfx_version" in header
    assert "gr_renderer_pygfx_capabilities_json" in header
    assert "gr_renderer_pygfx_backend_info_json" in header
    assert "gr_renderer_pygfx_adapter_bridge_json" in header
    assert '"renderer_backend":true' in implementation
    assert '"backend":"pygfx"' in implementation
    assert '"python_adapter_required":true' in implementation
    assert '"native_device_owner":false' in implementation
    assert '"fallback_backend":"python_pygfx"' in implementation


def test_renderer_d3d12_exports_descriptor_allocator_readiness_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
    ).read_text(encoding="utf-8")

    assert "gr_renderer_d3d12_descriptor_allocator_readiness_json" in header
    assert "renderer_d3d12_descriptor_allocator_readiness.v1" in implementation
    assert "CreateDescriptorHeap" in implementation
    assert "CreateCommandAllocator" in implementation
    assert '"draw_submission_enabled":false' in implementation


def test_renderer_d3d12_capabilities_report_complete_guarded_metadata_surface() -> None:
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
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


def test_renderer_d3d12_exports_command_list_readiness_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
    ).read_text(encoding="utf-8")

    assert "gr_renderer_d3d12_command_list_readiness_json" in header
    assert "renderer_d3d12_command_list_readiness.v1" in implementation
    assert "CreateCommandList" in implementation
    assert "command_list->Close()" in implementation
    assert '"app_commands_recorded":false' in implementation
    assert '"command_list_executed":false' in implementation
    assert '"draw_submission_enabled":false' in implementation


def test_renderer_d3d12_exports_surface_swap_chain_readiness_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
    ).read_text(encoding="utf-8")

    assert "gr_renderer_d3d12_surface_swap_chain_readiness_json" in header
    assert "renderer_d3d12_surface_swap_chain_readiness.v1" in implementation
    assert '"surface_handle_type":"HWND"' in implementation
    assert '"native_window_handle_ready":false' in implementation
    assert '"swap_chain_created":false' in implementation
    assert '"present_enabled":false' in implementation
    assert '"draw_submission_enabled":false' in implementation


def test_renderer_d3d12_exports_render_target_metadata_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
    ).read_text(encoding="utf-8")

    assert "gr_renderer_d3d12_render_target_metadata_json" in header
    assert "renderer_d3d12_render_target_metadata.v1" in implementation
    assert "D3D12_DESCRIPTOR_HEAP_TYPE_RTV" in implementation
    assert '"expected_back_buffer_count":2' in implementation
    assert '"back_buffers_acquired":false' in implementation
    assert '"render_target_views_created":false' in implementation
    assert '"present_enabled":false' in implementation
    assert '"draw_submission_enabled":false' in implementation


def test_renderer_d3d12_exports_barrier_clear_pass_metadata_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
    ).read_text(encoding="utf-8")

    assert "gr_renderer_d3d12_barrier_clear_pass_metadata_json" in header
    assert "renderer_d3d12_barrier_clear_pass_metadata.v1" in implementation
    assert '"D3D12_RESOURCE_STATE_PRESENT"' in implementation
    assert '"D3D12_RESOURCE_STATE_RENDER_TARGET"' in implementation
    assert '"resource_barriers_recorded":false' in implementation
    assert '"clear_recorded":false' in implementation
    assert '"command_list_executed":false' in implementation
    assert '"draw_submission_enabled":false' in implementation


def test_renderer_d3d12_exports_command_recording_dry_run_frame_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
    ).read_text(encoding="utf-8")

    assert "gr_renderer_d3d12_command_recording_dry_run_frame_json" in header
    assert "renderer_d3d12_command_recording_dry_run_frame.v1" in implementation
    assert '"command_allocator_reset":false' in implementation
    assert '"command_list_reset":false' in implementation
    assert '"draw_calls_recorded":0' in implementation
    assert '"command_list_executed":false' in implementation
    assert '"draw_submission_enabled":false' in implementation


def test_renderer_d3d12_exports_guarded_command_recording_diagnostics_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
    ).read_text(encoding="utf-8")

    assert "gr_renderer_d3d12_guarded_command_recording_diagnostics_json" in header
    assert "renderer_d3d12_guarded_command_recording_diagnostics.v1" in implementation
    assert "command_allocator->Reset()" in implementation
    assert "command_list->Reset" in implementation
    assert "command_list->Close()" in implementation
    assert '"draw_calls_recorded":0' in implementation
    assert '"command_list_executed":false' in implementation
    assert '"draw_submission_enabled":false' in implementation


def test_renderer_d3d12_exports_no_draw_execution_fence_diagnostics_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
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


def test_renderer_d3d12_exports_present_readiness_metadata_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
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


def test_renderer_d3d12_exports_guarded_swap_chain_creation_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
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


def test_renderer_d3d12_exports_guarded_back_buffer_rtv_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
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


def test_renderer_d3d12_exports_guarded_barrier_clear_recording_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
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


def test_renderer_d3d12_exports_guarded_clear_pass_execution_fence_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
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


def test_renderer_d3d12_exports_post_clear_present_readiness_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
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


def test_renderer_d3d12_exports_guarded_present_call_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
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


def test_renderer_d3d12_exports_post_present_frame_accounting_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
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


def test_renderer_d3d12_exports_draw_list_readiness_metadata_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
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


def test_renderer_d3d12_exports_resource_binding_readiness_metadata_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
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


def test_renderer_d3d12_exports_pipeline_state_readiness_metadata_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
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


def test_renderer_d3d12_exports_guarded_shader_bytecode_metadata_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
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


def test_renderer_d3d12_exports_shader_reflection_input_layout_metadata_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
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


def test_renderer_d3d12_exports_guarded_root_signature_metadata_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
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


def test_renderer_d3d12_exports_guarded_pipeline_state_object_metadata_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
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


def test_renderer_d3d12_exports_guarded_draw_command_recording_metadata_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
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


def test_renderer_d3d12_exports_guarded_draw_submission_readiness_metadata_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
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


def test_renderer_d3d12_exports_guarded_post_draw_frame_accounting_readiness_metadata_boundary() -> None:
    header = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "native"
        / "GhostRigger.Core.Rendering.Backends.D3D12"
        / "GhostRiggerRendererD3D12.cpp"
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
    )


def test_native_debug_validator_projects_are_not_in_solution() -> None:
    solution = (ROOT / "GhostRigger.sln").read_text(encoding="utf-8")

    assert ".DEBUG" not in solution
    assert not list((ROOT / "native").glob("*.DEBUG"))
