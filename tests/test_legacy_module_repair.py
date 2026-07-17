"""Focused contracts for the recovered legacy-module workflow."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


def _install_payload_paths() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        text = str(item)
        if text not in sys.path:
            sys.path.insert(0, text)


def test_legacy_candidate_preserves_core_metadata_and_generates_missing_pth(tmp_path: Path) -> None:
    _install_payload_paths()

    from pykotor.resource.formats.erf import ERF, ERFType, write_erf
    from pykotor.resource.formats.gff import bytes_gff, read_gff
    from pykotor.resource.type import ResourceType
    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.workflow.legacy_module_repair import (
        LegacyModuleCandidateRequest,
        build_legacy_module_candidate,
    )

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="legacy01",
        game="K2",
    )
    build = build_authored_module(project)
    assert not build.blocking_issues
    room = next(iter(build.module.room_geometry))
    rooms_dir = tmp_path / "rooms"
    rooms_dir.mkdir()
    for restype in ("mdl", "mdx", "wok"):
        (rooms_dir / f"{room}.{restype}").write_bytes(build.resources[(room, restype)].data)

    source = ERF(ERFType.MOD)
    source.set_data("legacy01", ResourceType.ARE, build.resources[("legacy01", "are")].data)
    source.set_data("legacy01", ResourceType.GIT, build.resources[("legacy01", "git")].data)
    source_ifo = read_gff(build.resources[("module", "ifo")].data)
    source_ifo.root.set_resref("Mod_OnHeartbeat", "legacy_hook")
    source.set_data("module", ResourceType.IFO, bytes_gff(source_ifo))
    source.set_data("legacy01", ResourceType.LYT, build.resources[("legacy01", "lyt")].data)
    source.set_data("legacy01", ResourceType.VIS, build.resources[("legacy01", "vis")].data)
    source.set_data("legacy01", ResourceType.PTH, build.resources[("legacy01", "pth")].data)
    source_mod = tmp_path / "source.mod"
    write_erf(source, source_mod)

    result = build_legacy_module_candidate(
        LegacyModuleCandidateRequest(
            module_resref="legacy01",
            target_game="K2",
            repaired_rooms_dir=str(rooms_dir),
            output_dir=str(tmp_path / "candidate"),
            source_mod=str(source_mod),
            regenerate_pth=True,
        )
    )

    assert result.ok, result.blocking_issues
    assert result.engine_contract["export_ready"] is True
    assert result.readback_contract["export_ready"] is True
    assert "legacy01.pth" in result.generated_resources
    assert any("deliberately replaced" in warning for warning in result.warnings)
    assert Path(result.module_path).is_file()
    assert Path(result.manifest_path).is_file()

    from pykotor.extract.capsule import LazyCapsule

    packaged_ifo = LazyCapsule(result.module_path).resource("module", ResourceType.IFO)
    assert packaged_ifo is not None
    assert str(read_gff(packaged_ifo).root.acquire("Mod_OnHeartbeat", "")).lower() == "legacy_hook"


def test_legacy_candidate_accepts_loose_core_sources_and_recursive_resources(tmp_path: Path) -> None:
    _install_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.workflow.legacy_module_repair import (
        LegacyModuleCandidateRequest,
        build_legacy_module_candidate,
    )

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="loose01",
        game="K1",
    )
    build = build_authored_module(project)
    assert not build.blocking_issues
    room = next(iter(build.module.room_geometry))
    rooms_dir = tmp_path / "rooms"
    rooms_dir.mkdir()
    for restype in ("mdl", "mdx", "wok"):
        (rooms_dir / f"{room}.{restype}").write_bytes(build.resources[(room, restype)].data)

    core_dir = tmp_path / "loose_core"
    core_dir.mkdir()
    core_paths: dict[str, Path] = {}
    for resref, restype in (
        ("loose01", "are"),
        ("loose01", "git"),
        ("module", "ifo"),
        ("loose01", "lyt"),
        ("loose01", "vis"),
    ):
        path = core_dir / f"{resref}.{restype}"
        path.write_bytes(build.resources[(resref, restype)].data)
        core_paths[restype] = path

    extras = tmp_path / "extras"
    extras.mkdir()
    (extras / "legacy_tex.txi").write_text("blending additive\n", encoding="ascii")
    (extras / "README.txt").write_text("source notes", encoding="utf-8")

    result = build_legacy_module_candidate(
        LegacyModuleCandidateRequest(
            module_resref="loose01",
            target_game="K1",
            repaired_rooms_dir=str(rooms_dir),
            output_dir=str(tmp_path / "candidate"),
            source_are=str(core_paths["are"]),
            source_git=str(core_paths["git"]),
            source_ifo=str(core_paths["ifo"]),
            source_lyt=str(core_paths["lyt"]),
            source_vis=str(core_paths["vis"]),
            extra_resource_dirs=(str(extras),),
        )
    )

    assert result.ok, result.blocking_issues
    bundled = {(row["resref"], row["restype"]) for row in result.bundled_resources}
    assert ("legacy_tex", "txi") in bundled
    assert all(restype != "txt" for _resref, restype in bundled)
    assert "loose01.pth" in result.generated_resources


def test_legacy_room_repair_missing_inputs_writes_a_blocker_manifest(tmp_path: Path) -> None:
    _install_payload_paths()

    from src.core.workflow.legacy_module_repair import (
        LegacyRoomRepairRequest,
        repair_legacy_room_with_mdlops,
    )

    result = repair_legacy_room_with_mdlops(
        LegacyRoomRepairRequest(
            room_resref="missing01",
            source_mdl=str(tmp_path / "missing01.mdl"),
            target_game="K1",
            output_dir=str(tmp_path / "output"),
            mdlops_executable=str(tmp_path / "mdlops.exe"),
        )
    )
    assert result.ok is False
    assert result.code == "input_missing"
    assert result.blocking_issues
    assert Path(result.manifest_path).is_file()
