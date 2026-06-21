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
    assert sum(row["python_file_count"] for row in payload_rows) == 1118
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
