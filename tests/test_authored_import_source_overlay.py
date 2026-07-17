"""Imported stock modules retain their complete capsule resource inventory."""

from __future__ import annotations

import os
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        value = str(item)
        if value not in sys.path:
            sys.path.insert(0, value)


def test_import_source_capsule_is_retained_with_generated_and_authored_overlay_precedence(tmp_path: Path) -> None:
    _configure_native_python_roots()

    from pykotor.extract.capsule import LazyCapsule
    from pykotor.resource.formats.rim import RIM, write_rim
    from pykotor.resource.type import ResourceType
    from src.core.modules.authored_module_export import AuthoredModuleExportRequest, export_authored_module_project
    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        create_dev_test_authored_module_payload,
    )

    module_root = "grsrcov"
    source_path = tmp_path / "source.rim"
    companion_path = tmp_path / "source_s.rim"
    source = RIM()
    source_rows = {
        ("keep_door", ResourceType.UTD): b"source-utd",
        ("keep_place", ResourceType.UTP): b"source-utp",
        ("keep_sound", ResourceType.UTS): b"source-uts",
        ("mystery", ResourceType.NCS): b"source-unknown-to-map-studio",
        ("replace_me", ResourceType.UTP): b"source-replaced-utp",
        (module_root, ResourceType.ARE): b"stale-source-are",
        (module_root, ResourceType.GIT): b"stale-source-git",
        ("module", ResourceType.IFO): b"stale-source-ifo",
        (module_root, ResourceType.LYT): b"stale-source-lyt",
        (module_root, ResourceType.VIS): b"stale-source-vis",
        (module_root, ResourceType.PTH): b"stale-source-pth",
    }
    for (resref, restype), data in source_rows.items():
        source.set_data(resref, restype, data)
    write_rim(source, source_path)
    companion = RIM()
    companion.set_data("companion_only", ResourceType.NCS, b"companion-script")
    companion.set_data("mystery", ResourceType.NCS, b"lower-precedence-mystery")
    write_rim(companion, companion_path)

    payload = create_dev_test_authored_module_payload(module_root=module_root, game="K2")
    project = authored_project_from_kmap_payload(payload, fallback_name=module_root, fallback_game="K2")
    project = replace(project, extra={**dict(project.extra), "import_source": str(source_path)})

    authored_replacement = b"authored-extra-utp"
    result = export_authored_module_project(
        AuthoredModuleExportRequest(
            project=project,
            output_dir=str(tmp_path / "export"),
            extra_resources=(("replace_me", "utp", authored_replacement),),
        )
    )
    assert result.ok, result.blocking_issues

    archive_rows = [
        ((str(resource.resname()).lower(), resource.restype().extension.lower()), bytes(resource.data()))
        for resource in LazyCapsule(result.module_path)
    ]
    archive = dict(archive_rows)
    assert archive[("keep_door", "utd")] == b"source-utd"
    assert archive[("keep_place", "utp")] == b"source-utp"
    assert archive[("keep_sound", "uts")] == b"source-uts"
    assert archive[("mystery", "ncs")] == b"source-unknown-to-map-studio"
    assert archive[("companion_only", "ncs")] == b"companion-script"
    assert archive[("replace_me", "utp")] == authored_replacement
    assert sum(1 for key, _data in archive_rows if key == ("replace_me", "utp")) == 1

    # Generated core resources replace stale source rows by normalized key.
    for resref, restype in (
        (module_root, "are"),
        (module_root, "git"),
        ("module", "ifo"),
        (module_root, "lyt"),
        (module_root, "vis"),
        (module_root, "pth"),
    ):
        assert archive[(resref, restype)] != source_rows[(resref, ResourceType.from_extension(restype))]

    overlay = result.metadata["import_source_overlay"]
    assert overlay["source_resource_count"] == len(source_rows) + 1
    assert overlay["source_layer_count"] == 2
    assert overlay["source_layer_resource_count"] == len(source_rows) + 2
    assert overlay["source_layers"][0]["name"] == "companion_s_rim"
    assert overlay["source_layers"][1]["name"] == "main_import_source"
    assert overlay["source_layers"][1]["overrode_lower_precedence_count"] == 1
    assert overlay["preserved_resource_count"] == 5
    assert overlay["generated_replaced_resource_count"] == 6
    assert overlay["authored_extra_replaced_resource_count"] == 1
    assert overlay["replaced_resource_count"] == 7
    assert result.metadata["resource_collision_gate"]["ready"] is True
    assert result.metadata["resource_collision_gate"]["replaced_import_source_resource_count"] == 1


def test_import_source_blocks_resource_type_that_archive_writer_cannot_address_safely(tmp_path: Path) -> None:
    _configure_native_python_roots()

    from pykotor.resource.formats.rim import RIM, write_rim
    from pykotor.resource.type import ResourceType
    from src.core.modules.authored_module_export import _import_source_capsule_resources

    source_path = tmp_path / "unsupported.rim"
    source = RIM()
    # Type id zero has an extension but is not an addressable Odyssey archive
    # resource type for the MOD/RIM replacement writer.
    source.set_data("unsafe_zero", ResourceType.RES, b"must-not-be-silently-dropped")
    write_rim(source, source_path)

    resources, issues, _path, layers = _import_source_capsule_resources(
        SimpleNamespace(extra={"import_source": str(source_path)})
    )
    assert resources == {}
    assert len(issues) == 1
    assert "not writable through the MOD/RIM archive path" in issues[0]
    assert layers[0]["blocking_issue_count"] == 1
