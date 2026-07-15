from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.native_python_payload_generator import resource_name_for_packaged_path


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_MANIFEST = ROOT / "native" / "GhostRigger.PythonPayloadManifest.json"


def _payload_entries() -> list[dict[str, object]]:
    entries = json.loads(PAYLOAD_MANIFEST.read_text(encoding="utf-8"))
    assert isinstance(entries, list)
    return entries


def _native_text(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    if path.suffix in {".h", ".hpp"}:
        public_path = path.parent / "Public" / path.name
        if public_path.exists():
            return public_path.read_text(encoding="utf-8")
    if path.suffix == ".cpp":
        private_path = path.parent / "Private" / path.name
        if private_path.exists():
            return private_path.read_text(encoding="utf-8")
    return path.read_text(encoding="utf-8")


def test_python_payload_manifest_covers_every_python_source_and_dll_project() -> None:
    entries = _payload_entries()
    payload_files = [
        Path(file)
        for entry in entries
        for file in entry["files"]
    ]
    source_files = sorted(Path("src") / path.relative_to(ROOT / "src") for path in (ROOT / "src").rglob("*.py"))
    payload_projects = {str(entry["project"]) for entry in entries}
    dll_projects = {
        project.stem
        for project in (ROOT / "native").glob("GhostRigger*/GhostRigger*.vcxproj")
        if ".DEBUG" not in project.stem
        and "<ConfigurationType>DynamicLibrary</ConfigurationType>" in project.read_text(encoding="utf-8")
    }

    assert len(entries) == 18
    # 2026-07-14: the complete Scripting Suite plus package-local legacy
    # module-repair and exact vanilla-texture-port workflows add their typed
    # Workflow/GUI/Automation payloads.
    # The prepared live-topology evaluator is packaged by both Scene (owner)
    # and Tools (embedded consumer), adding two byte-identical payload rows.
    assert len(payload_files) == 1293
    assert set(source_files).issubset(set(payload_files))
    assert payload_projects == dll_projects


def test_bridge_payload_is_reduced_into_real_owner_packages() -> None:
    """Bridge is no longer a payload/project owner; Qt IPC and Unreal have real owners."""

    assert not (ROOT / "native" / "GhostRigger.Core.Bridge").exists()

    qt_project = ROOT / "native" / "GhostRigger.Core.Qt"
    unreal_project = ROOT / "native" / "GhostRigger.Core.Unreal"
    qt_payload = json.loads((qt_project / "GhostRiggerPythonPayload.json").read_text(encoding="utf-8"))
    unreal_payload = json.loads((unreal_project / "GhostRiggerPythonPayload.json").read_text(encoding="utf-8"))
    qt_packaged = {str(row["packaged_path"]) for row in qt_payload["files"]}
    unreal_packaged = {str(row["packaged_path"]) for row in unreal_payload["files"]}

    assert "Python/src/adapters/qt_ipc/__init__.py" in qt_packaged
    assert "Python/src/adapters/qt_ipc/threading.py" in qt_packaged
    assert unreal_packaged == {
        "Python/src/unreal/__init__.py",
        "Python/src/unreal/animation_retargeting.py",
        "Python/src/unreal/quinn.py",
    }
    assert not (unreal_project / "Python" / "src" / "adapters").exists()


def test_content_browser_panels_are_owned_by_gui_boundary_panels_only() -> None:
    """Content Browser workflow data must not duplicate the shared panel surface."""

    boundary_project = ROOT / "native" / "GhostRigger.Core.GUI.Display"
    workflow_project = ROOT / "native" / "GhostRigger.Core.Tools"
    panel_paths = (
        "Python/src/gui/panels/qt_content_browser_panel.py",
        "Python/src/gui/panels/qt_library_panel.py",
    )

    boundary_payload = json.loads((boundary_project / "GhostRiggerPythonPayload.json").read_text(encoding="utf-8"))
    workflow_payload = json.loads((workflow_project / "GhostRiggerPythonPayload.json").read_text(encoding="utf-8"))
    boundary_packaged = {str(row["packaged_path"]) for row in boundary_payload["files"]}
    workflow_packaged = {str(row["packaged_path"]) for row in workflow_payload["files"]}
    workflow_project_text = (workflow_project / "GhostRigger.Core.Tools.vcxproj").read_text(encoding="utf-8")

    for path in panel_paths:
        assert path in boundary_packaged
        assert path not in workflow_packaged
        assert not (workflow_project / path).exists()
        assert path.replace("/", "\\") not in workflow_project_text


def test_twoda_parser_is_owned_by_domain_core_templates_only() -> None:
    """Workflow 2DA Browser must consume the shared parser, not package a fork."""

    owner_project = ROOT / "native" / "GhostRigger.Core.IO"
    workflow_project = ROOT / "native" / "GhostRigger.Core.Tools"
    parser_paths = (
        "Python/src/core/templates/__init__.py",
        "Python/src/core/templates/twoda.py",
    )

    owner_payload = json.loads((owner_project / "GhostRiggerPythonPayload.json").read_text(encoding="utf-8"))
    workflow_payload = json.loads((workflow_project / "GhostRiggerPythonPayload.json").read_text(encoding="utf-8"))
    owner_packaged = {str(row["packaged_path"]) for row in owner_payload["files"]}
    workflow_packaged = {str(row["packaged_path"]) for row in workflow_payload["files"]}
    workflow_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            workflow_project / "GhostRigger.Core.Tools.vcxproj",
            workflow_project / "GhostRigger.Core.Tools.vcxproj.filters",
            *sorted((workflow_project / "Private" / "PythonFunctions").glob("*.cpp")),
            *sorted((workflow_project / "Public" / "PythonFunctions").glob("*.h")),
        ]
        if path.exists()
    )

    for path in parser_paths:
        assert path in owner_packaged
        assert path not in workflow_packaged
        assert not (workflow_project / path).exists()
        assert path not in workflow_sources
        assert path.replace("/", "\\") not in workflow_sources


def test_reusable_workflow_payloads_are_owned_by_workflow_not_tools() -> None:
    """Tools must consume reusable workflow packages instead of repackaging forks."""

    owner_project = ROOT / "native" / "GhostRigger.Core.Workflow"
    tools_project = ROOT / "native" / "GhostRigger.Core.Tools"
    workflow_prefixes = (
        "Python/src/core/animation/",
        "Python/src/core/characters/",
        "Python/src/core/retargeting/",
    )

    owner_payload = json.loads((owner_project / "GhostRiggerPythonPayload.json").read_text(encoding="utf-8"))
    tools_payload = json.loads((tools_project / "GhostRiggerPythonPayload.json").read_text(encoding="utf-8"))
    owner_packaged = {str(row["packaged_path"]) for row in owner_payload["files"]}
    tools_packaged = {str(row["packaged_path"]) for row in tools_payload["files"]}
    tools_project_text = (
        (tools_project / "GhostRigger.Core.Tools.vcxproj").read_text(encoding="utf-8")
        + "\n"
        + (tools_project / "GhostRigger.Core.Tools.vcxproj.filters").read_text(encoding="utf-8")
    )

    for path in sorted(owner_packaged):
        if not path.startswith(workflow_prefixes):
            continue
        assert path not in tools_packaged
        assert not (tools_project / path).exists()
        assert path.replace("/", "\\") not in tools_project_text


def test_duplicate_renderer_contract_payloads_are_byte_identical() -> None:
    """Duplicate import names cannot depend on unsorted DLL discovery order."""

    packaged_path = Path("Python/src/core/rendering/mesh_render_data.py")
    rendering_copy = ROOT / "native" / "GhostRigger.Core.Rendering" / packaged_path
    runtime_shared_copy = ROOT / "native" / "GhostRigger.Runtime.Shared" / packaged_path

    assert rendering_copy.is_file()
    assert runtime_shared_copy.is_file()
    assert runtime_shared_copy.read_bytes() == rendering_copy.read_bytes()


def test_python_payload_copies_are_byte_identical_and_manifested() -> None:
    for entry in _payload_entries():
        project = str(entry["project"])
        project_dir = ROOT / "native" / project
        project_manifest = project_dir / "GhostRiggerPythonPayload.json"
        rc_file = project_dir / "GhostRiggerPythonPayload.rc"

        payload = json.loads(project_manifest.read_text(encoding="utf-8"))
        rc_text = rc_file.read_text(encoding="utf-8")

        assert payload["schema"] == "ghostrigger_python_payload.v1"
        assert payload["project"] == project
        assert payload["file_count"] == entry["python_file_count"]
        assert "PYTHON_PAYLOAD_MANIFEST RCDATA" in rc_text

        payload_rows = payload["files"]
        assert len(payload_rows) == entry["python_file_count"]
        for row in payload_rows:
            source = ROOT / row["source_path"]
            packaged = project_dir / row["packaged_path"]
            assert packaged.exists(), packaged
            if source.exists():
                assert packaged.read_bytes() == source.read_bytes()
            assert hashlib.sha256(packaged.read_bytes()).hexdigest() == row["sha256"]
            assert f'{row["resource_name"]} RCDATA' in rc_text


def test_shared_geometry_imports_use_embedded_src_namespace() -> None:
    """Payload manifests register Python/src modules below the ``src`` package."""

    runtime_import_paths = (
        ROOT / "native/GhostRigger.Core.Scene/Python/src/core/modules/authored_imported_mesh.py",
        ROOT / "native/GhostRigger.Core.Scene/Python/src/core/modules/authored_room_composition.py",
        ROOT / "native/GhostRigger.Core.Scene/Python/src/core/modules/authored_room_operations.py",
        ROOT / "native/GhostRigger.Core.Tools/Python/src/core/modules/authored_imported_mesh.py",
        ROOT / "native/GhostRigger.Core.Tools/Python/src/core/modules/authored_room_composition.py",
        ROOT / "native/GhostRigger.Core.Tools/Python/src/core/modules/authored_room_operations.py",
        ROOT / "native/GhostRigger.Core.Tools/Python/src/mesh_tools/mesh_topology.py",
    )
    offenders: list[str] = []
    for path in runtime_import_paths:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if re.match(r"(?:from|import)\s+core\.geometry(?:\.|\s|$)", line):
                offenders.append(f"{path.relative_to(ROOT)}:{line_number}: {line.strip()}")

    assert offenders == [], "Bare core.geometry imports bypass the embedded src namespace:\n" + "\n".join(offenders)


def test_native_source_fallback_imports_qt_main_window() -> None:
    """Reproduce the root executable's source fallback without adding Python/src."""

    script = r"""
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path[:] = [
    item
    for item in sys.path
    if not ((Path(item or '.').resolve() == root) or (root in Path(item or '.').resolve().parents))
]
source_roots = [root]
for project_dir in sorted((root / 'native').glob('GhostRigger*')):
    python_root = project_dir / 'Python'
    if (python_root / 'src').is_dir():
        source_roots.append(python_root)
for source_root in reversed(source_roots):
    sys.path.insert(0, str(source_root))

from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow, run

assert QtGhostRiggerMainWindow is not None
assert callable(run)
"""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-c", script, str(ROOT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_python_payload_resource_names_are_path_named() -> None:
    numbered_pattern = re.compile(r"^PYTHON_PAYLOAD_[0-9]+$")
    for entry in _payload_entries():
        project = str(entry["project"])
        project_dir = ROOT / "native" / project
        payload = json.loads((project_dir / "GhostRiggerPythonPayload.json").read_text(encoding="utf-8"))
        names = [str(row["resource_name"]) for row in payload["files"]]

        assert len(names) == len(set(names)), project
        for row in payload["files"]:
            resource_name = str(row["resource_name"])
            assert resource_name == resource_name_for_packaged_path(str(row["packaged_path"]))
            assert not numbered_pattern.fullmatch(resource_name)
            assert re.fullmatch(r"PYTHON_PAYLOAD_[A-Z0-9_]+", resource_name)


def test_native_projects_include_project_local_payload_generator() -> None:
    for entry in _payload_entries():
        project = str(entry["project"])
        project_dir = ROOT / "native" / project
        generator = project_dir / "GeneratePythonPayload.py"
        assert generator.exists(), generator

        vcxproj = (project_dir / f"{project}.vcxproj").read_text(encoding="utf-8")
        filters = (project_dir / f"{project}.vcxproj.filters").read_text(encoding="utf-8")
        generator_text = generator.read_text(encoding="utf-8")

        assert f'PROJECT = "{project}"' in generator_text
        assert "from scripts.native_python_payload_generator import generate_project" in generator_text
        assert '<None Include="GeneratePythonPayload.py" />' in vcxproj
        assert '<None Include="GeneratePythonPayload.py" />' in filters
        assert '<PropertyGroup Label="PythonPayloadBuild">' in vcxproj
        assert '$(GHOSTRIGGER_PYTHON)' in vcxproj
        assert 'Name="GenerateGhostRiggerPythonPayload" BeforeTargets="PrepareForBuild"' in vcxproj
        assert 'Command="&quot;$(GhostRiggerPythonPayloadPython)&quot; &quot;$(ProjectDir)GeneratePythonPayload.py&quot;"' in vcxproj


def test_python_payloads_are_included_in_visual_studio_projects() -> None:
    for entry in _payload_entries():
        project = str(entry["project"])
        project_dir = ROOT / "native" / project
        vcxproj = (project_dir / f"{project}.vcxproj").read_text(encoding="utf-8")

        assert '<ItemGroup Label="PythonPayload">' in vcxproj
        assert '<ResourceCompile Include="GhostRiggerPythonPayload.rc" />' in vcxproj
        assert '<None Include="GhostRiggerPythonPayload.json" />' in vcxproj
        for source in entry["files"]:
            include_path = f"Python\\{source}"
            assert f'<None Include="{include_path}" />' in vcxproj


def test_payload_dlls_export_common_python_payload_abi() -> None:
    for entry in _payload_entries():
        project = str(entry["project"])
        project_dir = ROOT / "native" / project
        cpp_text = "\n".join(path.read_text(encoding="utf-8") for path in project_dir.rglob("*.cpp"))

        assert "GhostRiggerPythonPayloadResource.h" in cpp_text
        assert "gr_python_payload_manifest_json" in cpp_text
        assert "gr_python_payload_file_count" in cpp_text
        assert "manifest_json_from_module_symbol" in cpp_text


def test_native_host_depends_on_every_payload_dll_project_without_linking_libs() -> None:
    entries = _payload_entries()
    host_project = ROOT / "native" / "GhostRigger.Native.Core.Host" / "GhostRigger.Native.Core.Host.vcxproj"
    tree = ET.parse(host_project)
    ns = {"msb": "http://schemas.microsoft.com/developer/msbuild/2003"}

    refs = {
        Path(node.attrib["Include"]).stem: node
        for node in tree.findall(".//msb:ItemGroup[@Label='NativePayloadDependencies']/msb:ProjectReference", ns)
    }

    assert set(refs) == {str(entry["project"]) for entry in entries}
    for node in refs.values():
        link_node = node.find("msb:LinkLibraryDependencies", ns)
        assert link_node is not None
        assert link_node.text == "false"


def test_native_host_stages_every_built_payload_dll_beside_both_developer_launchers() -> None:
    host_project = ROOT / "native" / "GhostRigger.Native.Core.Host" / "GhostRigger.Native.Core.Host.vcxproj"
    project_text = host_project.read_text(encoding="utf-8")
    staging_script = ROOT / "scripts" / "stage_native_payload_dlls.ps1"

    assert staging_script.is_file()
    assert project_text.count("stage_native_payload_dlls.ps1") == 2
    assert '-RepoRoot "$(GhostRiggerRepoRoot)."' in project_text
    assert '-HostOutDir "$(OutDir)."' in project_text
    assert "Get-ChildItem -LiteralPath '$(GhostRiggerRepoRoot)native'" not in project_text


def test_native_host_dependency_table_covers_every_payload_project() -> None:
    entries = _payload_entries()
    dependency_header = (
        ROOT / "native" / "GhostRigger.Native.Core.Host" / "GhostRiggerNativeDependencies.h"
    )
    dependency_header_text = _native_text(dependency_header)

    dependency_names = set(re.findall(r'\{L"(GhostRigger[^"]+)", L"GhostRigger[^"]+\.dll"', dependency_header_text))

    assert dependency_names == {str(entry["project"]) for entry in entries}
    assert "kNativeDependencySpecs" in dependency_header_text
    assert "kNativeDependencySpecCount" in dependency_header_text


def test_native_host_logs_dependency_audit_before_python_startup() -> None:
    main_source = (ROOT / "native" / "GhostRigger.Native.Core.Host" / "main.py").read_text(encoding="utf-8")
    host_source = _native_text(ROOT / "native" / "GhostRigger.Native.Core.Host" / "main.cpp")

    assert "GHOSTRIGGER_NATIVE_DEPENDENCY_AUDIT_JSON" not in main_source
    assert "_log_native_dependency_audit" not in main_source
    assert "GhostRigger Native dependency audit" in host_source
    assert "print_native_log_line" in host_source
    assert "Native DLL dependency " in host_source
    assert "utf8_from_wstring(row.dll_name)" in host_source
    assert "payload_files=" not in host_source
    assert "log_native_dependency_audit_to_console(*exe_dir)" in host_source
    assert host_source.index("log_native_dependency_audit_to_console(*exe_dir)") < host_source.index(
        "return run_embedded_python"
    )


def test_native_projects_use_public_private_python_layout() -> None:
    for entry in _payload_entries():
        project = str(entry["project"])
        project_dir = ROOT / "native" / project
        vcxproj = (project_dir / f"{project}.vcxproj").read_text(encoding="utf-8")

        assert (project_dir / "Public").is_dir()
        assert (project_dir / "Private").is_dir()
        assert (project_dir / "Python").is_dir()
        assert "ClInclude Include=\"Public\\" in vcxproj
        assert "ClCompile Include=\"Private\\" in vcxproj
        assert "None Include=\"Python\\" in vcxproj


def test_native_projects_have_python_function_migration_sources() -> None:
    category_names = {
        "async_instance_methods": "AsyncInstanceMethods",
        "async_module_functions": "AsyncModuleFunctions",
        "async_nested_functions": "AsyncNestedFunctions",
        "class_methods": "ClassMethods",
        "instance_methods": "InstanceMethods",
        "module_functions": "ModuleFunctions",
        "nested_functions": "NestedFunctions",
        "properties": "Properties",
        "static_methods": "StaticMethods",
    }

    for entry in _payload_entries():
        project = str(entry["project"])
        project_dir = ROOT / "native" / project
        vcxproj = (project_dir / f"{project}.vcxproj").read_text(encoding="utf-8")
        python_root = project_dir / "Python"

        expected_categories: set[str] = set()
        python_function_count = 0
        for source in python_root.rglob("*.py"):
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            parents: dict[ast.AST, ast.AST] = {}
            for parent in ast.walk(tree):
                for child in ast.iter_child_nodes(parent):
                    parents[child] = parent

            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                python_function_count += 1
                is_async = isinstance(node, ast.AsyncFunctionDef)
                ancestors: list[ast.AST] = []
                parent = parents.get(node)
                while parent is not None:
                    ancestors.append(parent)
                    parent = parents.get(parent)
                decorators = {
                    getattr(
                        decorator.func if isinstance(decorator, ast.Call) else decorator,
                        "id",
                        getattr(
                            decorator.func if isinstance(decorator, ast.Call) else decorator,
                            "attr",
                            "",
                        ),
                    )
                    for decorator in node.decorator_list
                }
                if any(isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)) for parent in ancestors):
                    expected_categories.add("async_nested_functions" if is_async else "nested_functions")
                elif any(isinstance(parent, ast.ClassDef) for parent in ancestors):
                    if "property" in decorators or "setter" in decorators or "deleter" in decorators:
                        expected_categories.add("properties")
                    elif "staticmethod" in decorators:
                        expected_categories.add("static_methods")
                    elif "classmethod" in decorators:
                        expected_categories.add("class_methods")
                    else:
                        expected_categories.add("async_instance_methods" if is_async else "instance_methods")
                else:
                    expected_categories.add("async_module_functions" if is_async else "module_functions")

        public_root = project_dir / "Public" / "PythonFunctions"
        private_root = project_dir / "Private" / "PythonFunctions"
        public_headers = sorted(public_root.glob("*.h")) if public_root.exists() else []
        private_sources = sorted(private_root.glob("*.cpp")) if private_root.exists() else []

        if python_function_count == 0:
            assert not public_headers
            assert not private_sources
            assert '<ItemGroup Label="NativeFunctionImplementations">' not in vcxproj
            continue

        expected_file_names = {f"{category_names[category]}.h" for category in expected_categories}
        expected_source_names = {f"{category_names[category]}.cpp" for category in expected_categories}
        assert public_headers
        assert private_sources
        assert {path.name for path in public_headers} <= expected_file_names
        assert {path.name for path in private_sources} <= expected_source_names
        assert '<ItemGroup Label="NativeFunctionImplementations">' in vcxproj
        assert "PythonFunctions\\**" not in vcxproj
        assert "pyfn_" not in vcxproj
        assert "phase15" not in vcxproj
        assert "PythonFunctionMigration" not in vcxproj
        assert not list(public_root.rglob("fn_*.h"))
        assert not list(private_root.rglob("fn_*.cpp"))

        native_contract_count = 0
        for private_source in private_sources:
            source_text = private_source.read_text(encoding="utf-8")
            native_contract_count += source_text.count('"schema":"ghostrigger.native.cpp_function.v1"')
            assert "_native()" in source_text
            assert "NativeFunctionImplementation entries[]" in source_text
            assert "phase15" not in source_text
            assert "descriptor_json" not in source_text
            assert '"python_runtime_required":false' in source_text
            assert '"native_first":true' in source_text
            source_item = str(private_source.relative_to(project_dir)).replace("/", "\\")
            assert f'<ClCompile Include="{source_item}"' in vcxproj
        assert native_contract_count <= python_function_count
        assert native_contract_count > 0

        for public_header in public_headers:
            header_text = public_header.read_text(encoding="utf-8")
            assert "NativeFunctionImplementation" in header_text
            assert "_native();" in header_text
            assert "phase15" not in header_text
            assert "descriptor_json" not in header_text
            header_item = str(public_header.relative_to(project_dir)).replace("/", "\\")
            assert f'<ClInclude Include="{header_item}"' in vcxproj


def test_native_visual_studio_projects_do_not_use_wildcard_items() -> None:
    wildcard_pattern = re.compile(r'Include="[^"]*[*]')
    for project_file in (ROOT / "native").rglob("*.vcxproj"):
        text = project_file.read_text(encoding="utf-8")
        assert "PythonFunctions\\**" not in text
        assert "PythonFunctionMigration" not in text
        assert not wildcard_pattern.search(text), project_file


def test_native_visual_studio_filters_expose_public_private_python_folders() -> None:
    ns = {"msb": "http://schemas.microsoft.com/developer/msbuild/2003"}
    for project_file in (ROOT / "native").glob("GhostRigger*/GhostRigger*.vcxproj"):
        project_dir = project_file.parent
        filters_file = project_file.with_suffix(project_file.suffix + ".filters")
        assert filters_file.exists(), filters_file

        filters_tree = ET.parse(filters_file)
        filters = {
            node.attrib["Include"]
            for node in filters_tree.findall(".//msb:Filter", ns)
            if "Include" in node.attrib
        }
        project_text = project_file.read_text(encoding="utf-8")

        if "ClInclude Include=\"Public\\" in project_text or (project_dir / "Public").is_dir():
            assert "Public" in filters
        if "ClCompile Include=\"Private\\" in project_text or (project_dir / "Private").is_dir():
            assert "Private" in filters
        if "None Include=\"Python\\" in project_text or (project_dir / "Python").is_dir():
            assert "Python" in filters
