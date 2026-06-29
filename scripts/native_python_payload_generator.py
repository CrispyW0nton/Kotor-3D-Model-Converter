"""Generate per-project embedded Python payload manifests and RC resources."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NATIVE_ROOT = ROOT / "native"
ROOT_MANIFEST = NATIVE_ROOT / "GhostRigger.PythonPayloadManifest.json"


def write_text_if_changed(path: Path, text: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    path.write_text(text, encoding="utf-8")


def resource_name_for_packaged_path(packaged_path: str) -> str:
    """Return a readable RC identifier for a packaged Python payload path."""

    normalized = str(packaged_path).replace("\\", "/")
    if normalized.startswith("Python/"):
        normalized = normalized[len("Python/") :]
    if normalized.startswith("src/"):
        normalized = normalized[len("src/") :]
    if normalized.endswith(".py"):
        normalized = normalized[:-3]
    normalized = normalized.replace("__init__", "init")
    token = re.sub(r"[^0-9A-Za-z]+", "_", normalized).strip("_").upper()
    return f"PYTHON_PAYLOAD_{token or 'MODULE'}"


def load_root_entries() -> dict[str, dict]:
    entries = json.loads(ROOT_MANIFEST.read_text(encoding="utf-8"))
    return {str(entry["project"]): entry for entry in entries}


def project_entry(project: str) -> dict:
    entries = load_root_entries()
    if project not in entries:
        raise SystemExit(f"unknown native Python payload project: {project}")
    return entries[project]


def project_python_files(project: str) -> list[Path]:
    project_dir = NATIVE_ROOT / project
    python_root = project_dir / "Python"
    files = [
        path.relative_to(python_root)
        for path in (python_root / "src").rglob("*.py")
        if path.is_file()
    ]
    return sorted(files, key=lambda path: path.as_posix().lower())


def refresh_root_manifest(projects: list[str] | None = None) -> None:
    entries = load_root_entries()
    target_projects = projects or sorted(entries)
    for project in target_projects:
        files = project_python_files(project)
        entries[project] = {
            "project": project,
            "python_file_count": len(files),
            "files": [path.as_posix().replace("/", "\\") for path in files],
        }
    ordered = [entries[project] for project in sorted(entries)]
    write_text_if_changed(ROOT_MANIFEST, json.dumps(ordered, indent=4) + "\n")


def generate_project(project: str) -> None:
    project_entry(project)
    project_dir = NATIVE_ROOT / project
    rows = []
    seen_names: dict[str, int] = {}
    for source_path in project_python_files(project):
        packaged_path = Path("Python") / source_path
        source_abs = ROOT / source_path
        packaged_abs = project_dir / packaged_path
        if not packaged_abs.exists():
            raise FileNotFoundError(packaged_abs)
        if source_abs.exists() and source_abs.read_bytes() != packaged_abs.read_bytes():
            raise RuntimeError(f"payload copy differs from source: {packaged_abs}")

        resource_name = resource_name_for_packaged_path(packaged_path.as_posix())
        count = seen_names.get(resource_name, 0)
        seen_names[resource_name] = count + 1
        if count:
            resource_name = f"{resource_name}_{count + 1}"

        rows.append(
            {
                "resource_name": resource_name,
                "source_path": source_path.as_posix(),
                "packaged_path": packaged_path.as_posix(),
                "sha256": hashlib.sha256(packaged_abs.read_bytes()).hexdigest(),
            }
        )

    manifest = {
        "schema": "ghostrigger_python_payload.v1",
        "phase": "P1.5 embedded python payload",
        "project": project,
        "file_count": len(rows),
        "originals_remain_in_src": True,
        "files": rows,
    }
    write_text_if_changed(
        project_dir / "GhostRiggerPythonPayload.json",
        json.dumps(manifest, indent=4) + "\n",
    )

    rc_lines = [
        "// Generated Phase 1.5 Python payload resources. Original Python files remain in src/.",
        'PYTHON_PAYLOAD_MANIFEST RCDATA "GhostRiggerPythonPayload.json"',
    ]
    rc_lines.extend(f'{row["resource_name"]} RCDATA "{row["packaged_path"]}"' for row in rows)
    write_text_if_changed(project_dir / "GhostRiggerPythonPayload.rc", "\n".join(rc_lines) + "\n")
    ensure_project_payload_items(project, [Path(row["packaged_path"]) for row in rows])


def ensure_project_payload_items(project: str, packaged_paths: list[Path]) -> None:
    project_dir = NATIVE_ROOT / project
    vcxproj = project_dir / f"{project}.vcxproj"
    if not vcxproj.exists():
        return

    text = vcxproj.read_text(encoding="utf-8")
    match = re.search(r'(<ItemGroup Label="PythonPayload">)(.*?)(</ItemGroup>)', text, flags=re.DOTALL)
    if not match:
        raise RuntimeError(f"cannot find Python payload item group in {vcxproj}")

    body = match.group(2)
    existing = set(re.findall(r'<None Include="([^"]+)"\s*/>', body))
    required = [
        str(path).replace("/", "\\")
        for path in packaged_paths
    ]
    missing = [
        item
        for item in required
        if item not in existing
    ]
    if not missing:
        return

    addition = "".join(f'<None Include="{item}" />' for item in missing)
    updated_group = f"{match.group(1)}{body}{addition}{match.group(3)}"
    updated = text[:match.start()] + updated_group + text[match.end():]
    write_text_if_changed(vcxproj, updated)


def _insert_after_once(text: str, anchor: str, addition: str, exists: str, path: Path) -> str:
    if exists in text:
        return text
    if anchor not in text:
        raise RuntimeError(f"cannot find insertion point in {path}")
    return text.replace(anchor, anchor + addition, 1)


def ensure_project_generator_items(project: str) -> None:
    project_dir = NATIVE_ROOT / project
    vcxproj = project_dir / f"{project}.vcxproj"
    filters = project_dir / f"{project}.vcxproj.filters"

    vcxproj_text = vcxproj.read_text(encoding="utf-8")
    vcxproj_text = _insert_after_once(
        vcxproj_text,
        '    <None Include="GhostRiggerPythonPayload.json" />',
        '\n    <None Include="GeneratePythonPayload.py" />',
        '<None Include="GeneratePythonPayload.py" />',
        vcxproj,
    )
    write_text_if_changed(vcxproj, vcxproj_text)

    filters_text = filters.read_text(encoding="utf-8")
    filters_text = _insert_after_once(
        filters_text,
        '    <None Include="GhostRiggerPythonPayload.json" />',
        '\n    <None Include="GeneratePythonPayload.py" />',
        '<None Include="GeneratePythonPayload.py" />',
        filters,
    )
    write_text_if_changed(filters, filters_text)


def ensure_project_build_target(project: str) -> None:
    project_dir = NATIVE_ROOT / project
    vcxproj = project_dir / f"{project}.vcxproj"
    vcxproj_text = vcxproj.read_text(encoding="utf-8")

    target = """  <PropertyGroup Label="PythonPayloadBuild">
    <GhostRiggerPythonPayloadPython Condition="'$(GhostRiggerPythonPayloadPython)'=='' and '$(GHOSTRIGGER_PYTHON)'!=''">$(GHOSTRIGGER_PYTHON)</GhostRiggerPythonPayloadPython>
    <GhostRiggerPythonPayloadPython Condition="'$(GhostRiggerPythonPayloadPython)'==''">python</GhostRiggerPythonPayloadPython>
  </PropertyGroup>
  <Target Name="GenerateGhostRiggerPythonPayload" BeforeTargets="PrepareForBuild" Condition="Exists('$(ProjectDir)GeneratePythonPayload.py')">
    <Message Importance="High" Text="Generating Python payload for $(MSBuildProjectName)" />
    <Exec Command="&quot;$(GhostRiggerPythonPayloadPython)&quot; &quot;$(ProjectDir)GeneratePythonPayload.py&quot;" />
  </Target>
"""
    if 'Name="GenerateGhostRiggerPythonPayload"' in vcxproj_text:
        updated = re.sub(
            r'  <PropertyGroup Label="PythonPayloadBuild">\n.*?  </Target>\n',
            target,
            vcxproj_text,
            count=1,
            flags=re.DOTALL,
        )
        if updated == vcxproj_text:
            raise RuntimeError(f"cannot replace Python payload build target in {vcxproj}")
        write_text_if_changed(vcxproj, updated)
        return

    anchor = '<Import Project="$(VCTargetsPath)\\Microsoft.Cpp.targets" />'
    if anchor not in vcxproj_text:
        raise RuntimeError(f"cannot find C++ targets import in {vcxproj}")
    write_text_if_changed(vcxproj, vcxproj_text.replace(anchor, target + anchor, 1))


def write_project_generator(project: str) -> None:
    project_dir = NATIVE_ROOT / project
    script = f'''"""Regenerate the embedded Python payload for {project}."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT = "{project}"
ROOT = Path(__file__).resolve().parents[1]
repo_root = ROOT.parent
sys.path.insert(0, str(repo_root))

from scripts.native_python_payload_generator import generate_project


if __name__ == "__main__":
    generate_project(PROJECT)
'''
    write_text_if_changed(project_dir / "GeneratePythonPayload.py", script)
    ensure_project_generator_items(project)
    ensure_project_build_target(project)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", help="Native project name to regenerate")
    parser.add_argument("--all", action="store_true", help="Regenerate every native Python payload project")
    parser.add_argument("--write-project-generators", action="store_true", help="Write project-local generator wrappers")
    args = parser.parse_args()

    projects = sorted(load_root_entries())
    if args.project:
        projects = [args.project]
    elif not args.all and not args.write_project_generators:
        raise SystemExit("pass a project name, --all, or --write-project-generators")

    if args.write_project_generators:
        for project in projects:
            write_project_generator(project)

    if args.all or args.project:
        refresh_root_manifest(projects)
        for project in projects:
            generate_project(project)


if __name__ == "__main__":
    main()
