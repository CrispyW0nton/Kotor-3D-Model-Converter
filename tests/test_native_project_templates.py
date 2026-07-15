from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "native" / "templates"
NAMESPACE_MANIFEST = ROOT / "knowledge_base" / "native_project_namespace_manifest.md"
PAYLOAD_MANIFEST = ROOT / "native" / "GhostRigger.PythonPayloadManifest.json"


EXPECTED_PROJECTS = {
    "GhostRigger.Core.Automation",
    "GhostRigger.Core.GUI.Display",
    "GhostRigger.Core.GUI.Helpers",
    "GhostRigger.Core.IO",
    "GhostRigger.Core.Math",
    "GhostRigger.Core.Project",
    "GhostRigger.Core.Qt",
    "GhostRigger.Core.Rendering",
    "GhostRigger.Core.Resources",
    "GhostRigger.Core.Scene",
    "GhostRigger.Core.Tools",
    "GhostRigger.Core.Unreal",
    "GhostRigger.Core.Validation",
    "GhostRigger.Core.Workflow",
    "GhostRigger.Native.Core.Foundation",
    "GhostRigger.Native.Core.Host",
    "GhostRigger.Runtime.Core",
    "GhostRigger.Runtime.Core.Host",
    "GhostRigger.Runtime.Shared",
}


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


def _manifest_project_rows() -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in NAMESPACE_MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `GhostRigger."):
            continue
        columns = [column.strip() for column in line.strip("|").split("|")]
        if len(columns) < 4:
            continue
        project_name = columns[0].strip("`")
        project_file = columns[2].strip("`")
        rows[project_name] = project_file
    return rows


def test_native_vcxproj_templates_parse_after_token_substitution() -> None:
    for template in TEMPLATE_DIR.glob("*.vcxproj.template"):
        rendered = _render_template(template)
        assert "{{" not in rendered
        ET.fromstring(rendered)


def test_solution_uses_collapsed_project_boundaries() -> None:
    solution = (ROOT / "GhostRigger.sln").read_text(encoding="utf-8")
    project_names = set(_solution_project_names(solution))

    assert project_names == EXPECTED_PROJECTS
    assert _solution_folder_names(solution) == []
    assert "GlobalSection(NestedProjects)" not in solution
    for project_name in EXPECTED_PROJECTS:
        assert f"native\\{project_name}\\{project_name}.vcxproj" in solution


def test_namespace_manifest_matches_solution_projects() -> None:
    rows = _manifest_project_rows()

    assert set(rows) == EXPECTED_PROJECTS
    for project_name, project_file in rows.items():
        assert project_file == f"native\\{project_name}\\{project_name}.vcxproj"


def test_payload_manifest_tracks_aggregate_payload_projects() -> None:
    payload_rows = json.loads(PAYLOAD_MANIFEST.read_text(encoding="utf-8"))
    payload_projects = {row["project"] for row in payload_rows}

    assert len(payload_projects) == 18
    assert payload_projects == EXPECTED_PROJECTS - {"GhostRigger.Native.Core.Host"}
    assert sum(row["python_file_count"] for row in payload_rows) == 1302
    assert all(not row["project"].endswith(".vcxproj") for row in payload_rows)


def test_native_docs_describe_final_collapsed_architecture() -> None:
    docs = "\n".join(
        [
            (ROOT / "AGENTS.md").read_text(encoding="utf-8"),
            (ROOT / "native" / "README.md").read_text(encoding="utf-8"),
            NAMESPACE_MANIFEST.read_text(encoding="utf-8"),
            (ROOT / "knowledge_base" / "package_ownership_model.md").read_text(
                encoding="utf-8"
            ),
        ]
    )

    assert "Real C++ projects in `GhostRigger.sln`: 19" in docs
    assert "Python-payload DLL projects" in docs
    assert "GhostRigger.Core.IO" in docs
    assert "GhostRigger.Core.Math" in docs
    assert "GhostRigger.Core.Qt" in docs
    assert "GhostRigger.Core.Unreal" in docs
    assert "GhostRigger.Core.Bridge" not in docs
    assert "Do not recreate split DLLs" in docs


def test_native_host_builds_ghoststudio_with_windows_branding_resources() -> None:
    host_dir = ROOT / "native" / "GhostRigger.Native.Core.Host"
    project = (host_dir / "GhostRigger.Native.Core.Host.vcxproj").read_text(encoding="utf-8")
    resource = (host_dir / "GhostRiggerNativeSplash.rc").read_text(encoding="utf-8")
    main_cpp = (host_dir / "Private" / "main.cpp").read_text(encoding="utf-8")
    app_runner = (
        ROOT
        / "native"
        / "GhostRigger.Core.GUI.Display"
        / "Python"
        / "src"
        / "gui"
        / "windows"
        / "application_core"
        / "functions"
        / "app_runner.py"
    ).read_text(encoding="utf-8")
    spec = (ROOT / "GhostRigger-K1-K2.spec").read_text(encoding="utf-8")
    build_script = (ROOT / "build.bat").read_text(encoding="utf-8")
    version_info = (ROOT / "assets" / "windows_version_info.txt").read_text(encoding="utf-8")
    icon = ROOT / "assets" / "icons" / "ghostrigger.ico"

    assert "<TargetName>GhostStudio</TargetName>" in project
    assert 'IDI_GHOSTSTUDIO_APP_ICON ICON "../../assets/icons/ghostrigger.ico"' in resource
    assert "VS_VERSION_INFO VERSIONINFO" in resource
    assert 'VALUE "ProductName", "GhostStudio\\0"' in resource
    assert 'VALUE "OriginalFilename", "GhostStudio.exe\\0"' in resource
    assert "executable_path()" in main_cpp
    assert 'L"GhostRigger.exe"' not in main_cpp
    assert 'app.setApplicationName("GhostStudio")' in app_runner
    assert 'app.setApplicationDisplayName("GhostStudio")' in app_runner

    assert "name='GhostStudio'" in spec
    assert "version='assets/windows_version_info.txt'" in spec
    assert "icon='assets/icons/ghostrigger.ico'" in spec
    assert "dist\\GhostStudio.exe" in build_script
    assert "StringStruct('ProductName', 'GhostStudio')" in version_info
    assert icon.read_bytes()[:4] == b"\x00\x00\x01\x00"
