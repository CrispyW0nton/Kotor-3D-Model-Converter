"""Focused contracts for the recovered legacy-module workflow."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _install_payload_paths() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        text = str(item)
        if text not in sys.path:
            sys.path.insert(0, text)


def test_pathing_wok_coordinate_policy_never_double_translates_module_space() -> None:
    _install_payload_paths()

    from src.core.modules.module_format import LYTRoom
    from src.core.workflow.legacy_module_repair import _room_wok_module_offset

    room = LYTRoom("koq200_01b", 123.0, -45.0, 6.0)
    assert _room_wok_module_offset(room, "module") == (0.0, 0.0, 0.0)
    assert _room_wok_module_offset(room, "world_space") == (0.0, 0.0, 0.0)
    assert _room_wok_module_offset(room, "room_local") == (123.0, -45.0, 6.0)


def test_walkmesh_transition_remap_preserves_retained_rooms_and_drops_omitted_rooms() -> None:
    _install_payload_paths()

    from src.core.modules.module_format import WOKData, WOKFace
    from src.core.workflow.legacy_module_repair import remap_walkmesh_transition_destinations
    from src.core.workflow.legacy_module_repair import (
        LegacyModuleCandidateRequest,
        LegacyModuleCandidateResult,
    )

    source_rooms = tuple(f"koq202_01{suffix}" for suffix in "abcdefghij")
    target_rooms = tuple(f"koq202_01{suffix}" for suffix in "abcdg")
    wok = WOKData(
        name="koq202_transition_fixture",
        verts=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[WOKFace(0, 1, 2, 1, trans1=6, trans2=7, trans3=2)],
    )

    rows = remap_walkmesh_transition_destinations(
        wok,
        source_room_resrefs=source_rooms,
        target_room_resrefs=target_rooms,
    )

    assert (wok.faces[0].trans1, wok.faces[0].trans2, wok.faces[0].trans3) == (4, -1, 2)
    assert [(row["source_target"], row["target_index"], row["action"]) for row in rows] == [
        ("koq202_01g", 4, "remapped"),
        ("koq202_01h", -1, "dropped"),
        ("koq202_01c", 2, "preserved"),
    ]
    request = LegacyModuleCandidateRequest(
        module_resref="koq202",
        target_game="K2",
        repaired_rooms_dir="rooms",
        output_dir="candidate",
        source_transition_room_resrefs=source_rooms,
    )
    result = LegacyModuleCandidateResult(source_transition_room_resrefs=list(source_rooms))
    assert request.to_dict()["source_transition_room_resrefs"] == source_rooms
    assert result.to_dict()["source_transition_room_resrefs"] == list(source_rooms)

    wok.faces[0].trans1 = len(source_rooms)
    with pytest.raises(ValueError, match="outside the 10-room source LYT ordering"):
        remap_walkmesh_transition_destinations(
            wok,
            source_room_resrefs=source_rooms,
            target_room_resrefs=target_rooms,
        )


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


def _pathing_room(name: str, x: float, y: float):
    from src.core.modules.authored_module_pathing import AuthoredPathingRoom
    from src.core.modules.module_format import WOKData, WOKFace

    wok = WOKData(
        name=name,
        verts=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0), (0.0, 2.0, 0.0)],
        faces=[WOKFace(0, 1, 2, 1), WOKFace(0, 2, 3, 1)],
    )
    wok.rebuild_adjacencies()
    return AuthoredPathingRoom(name, wok, (x, y, 0.0))


def _set_pathing_transition(room, side: str, target: int) -> None:
    # Square topology above: bottom=f0/e0, right=f0/e1,
    # top=f1/e1, left=f1/e2.
    face_index, local_edge = {
        "bottom": (0, 0),
        "right": (0, 1),
        "top": (1, 1),
        "left": (1, 2),
    }[side]
    setattr(room.wok.faces[face_index], f"trans{local_edge + 1}", target)


def _link_pathing_rooms(rooms: list, left: int, right: int, *, reciprocal: bool = True) -> None:
    ax, ay, _az = rooms[left].position
    bx, by, _bz = rooms[right].position
    delta = (round(bx - ax, 6), round(by - ay, 6))
    source_side, target_side = {
        (2.0, 0.0): ("right", "left"),
        (-2.0, 0.0): ("left", "right"),
        (0.0, 2.0): ("top", "bottom"),
        (0.0, -2.0): ("bottom", "top"),
    }[delta]
    _set_pathing_transition(rooms[left], source_side, right)
    if reciprocal:
        _set_pathing_transition(rooms[right], target_side, left)


def _cross_room_pathing_pairs(graph) -> set[tuple[int, int]]:
    result: set[tuple[int, int]] = set()
    for edge in graph.connections:
        source_room = int(graph.points[edge.source].metadata["room_index"])
        target_room = int(graph.points[edge.target].metadata["room_index"])
        if source_room != target_room:
            result.add((source_room, target_room))
    return result


def test_koq200_reciprocal_transition_tree_gets_bidirectional_pth_portals() -> None:
    _install_payload_paths()
    from src.core.modules.authored_module_pathing import compile_authored_pathing_for_rooms

    rooms = [
        _pathing_room("koq200_01a", 0.0, 0.0),
        _pathing_room("koq200_01b", 2.0, 0.0),
        _pathing_room("koq200_01c", 4.0, 0.0),
        _pathing_room("koq200_01d", 2.0, 2.0),
        _pathing_room("koq200_01e", 6.0, 0.0),
        _pathing_room("koq200_01f", 8.0, 0.0),
        _pathing_room("koq200_01g", 10.0, 0.0),
    ]
    pairs = {(0, 1), (1, 2), (1, 3), (2, 4), (4, 5), (5, 6)}
    for left, right in pairs:
        _link_pathing_rooms(rooms, left, right)

    compiled = compile_authored_pathing_for_rooms(tuple(rooms))

    assert compiled.validation.ok
    assert compiled.metadata["reciprocal_transition_pair_count"] == len(pairs)
    assert compiled.metadata["generated_portal_link_count"] == len(pairs)
    assert compiled.metadata["path_graph_component_count"] == 1
    assert _cross_room_pathing_pairs(compiled.graph) == pairs | {(right, left) for left, right in pairs}
    assert all(row["bidirectional_bridge_count"] >= 1 for row in compiled.metadata["reciprocal_transition_pairs"])
    assert compiled.pth_bytes.startswith(b"PTH ")


def test_koq201_one_way_transition_and_unlinked_rooms_remain_disconnected() -> None:
    _install_payload_paths()
    from src.core.modules.authored_module_pathing import compile_authored_pathing_for_rooms

    rooms = [
        _pathing_room("koq201_01a", 2.0, -2.0),
        _pathing_room("koq201_01b", 2.0, 0.0),
        _pathing_room("koq201_01c", 4.0, 0.0),
        _pathing_room("koq201_01d", 6.0, 0.0),
        _pathing_room("koq201_01e", 8.0, 0.0),
        _pathing_room("koq201_01f", 10.0, 0.0),
        _pathing_room("koq201_01g", 20.0, 0.0),
        _pathing_room("koq201_01h", 24.0, 0.0),
        _pathing_room("koq201_01j", 28.0, 0.0),
    ]
    reciprocal = {(1, 2), (2, 3), (3, 4), (4, 5)}
    for left, right in reciprocal:
        _link_pathing_rooms(rooms, left, right)
    _link_pathing_rooms(rooms, 1, 0, reciprocal=False)

    compiled = compile_authored_pathing_for_rooms(tuple(rooms))

    assert compiled.metadata["reciprocal_transition_pair_count"] == 4
    assert compiled.metadata["generated_portal_link_count"] == 4
    assert compiled.metadata["one_way_transition_count"] == 1
    assert compiled.metadata["path_graph_component_count"] == 5
    assert _cross_room_pathing_pairs(compiled.graph) == reciprocal | {
        (right, left) for left, right in reciprocal
    }
    assert (0, 1) not in _cross_room_pathing_pairs(compiled.graph)
    assert (1, 0) not in _cross_room_pathing_pairs(compiled.graph)


def test_koq202_remapped_retained_room_indices_link_and_island_stays_isolated() -> None:
    _install_payload_paths()
    from src.core.modules.authored_module_pathing import compile_authored_pathing_for_rooms

    rooms = [
        _pathing_room("koq202_01a", 0.0, 0.0),
        _pathing_room("koq202_01b", 2.0, 0.0),
        _pathing_room("koq202_01c", 0.0, 2.0),
        _pathing_room("koq202_01d", 20.0, 0.0),
        _pathing_room("koq202_01g", 0.0, 4.0),
    ]
    retained_pairs = {(0, 1), (0, 2), (2, 4)}
    for left, right in retained_pairs:
        _link_pathing_rooms(rooms, left, right)

    compiled = compile_authored_pathing_for_rooms(tuple(rooms))

    assert compiled.metadata["reciprocal_transition_pair_count"] == 3
    assert compiled.metadata["generated_portal_link_count"] == 3
    assert compiled.metadata["path_graph_component_count"] == 2
    assert _cross_room_pathing_pairs(compiled.graph) == retained_pairs | {
        (right, left) for left, right in retained_pairs
    }


def test_transition_pathing_blocks_stale_indices_mismatches_and_missing_reverse_edge() -> None:
    _install_payload_paths()
    from src.core.modules.authored_module_pathing import (
        compile_authored_pathing_for_rooms,
        validate_authored_room_path_graph,
    )

    stale = [_pathing_room(f"koq202_01{name}", float(index * 2), 0.0) for index, name in enumerate("abcdg")]
    _set_pathing_transition(stale[2], "right", 6)
    with pytest.raises(ValueError, match="targets missing LYT room index 6"):
        compile_authored_pathing_for_rooms(tuple(stale))

    mismatched = [_pathing_room("room_a", 0.0, 0.0), _pathing_room("room_b", 2.0, 0.1)]
    _set_pathing_transition(mismatched[0], "right", 1)
    _set_pathing_transition(mismatched[1], "left", 0)
    with pytest.raises(ValueError, match="no boundary-edge midpoint match"):
        compile_authored_pathing_for_rooms(tuple(mismatched))

    rooms = [_pathing_room("room_a", 0.0, 0.0), _pathing_room("room_b", 2.0, 0.0)]
    _link_pathing_rooms(rooms, 0, 1)
    compiled = compile_authored_pathing_for_rooms(tuple(rooms))
    portal = compiled.graph.metadata["portal_links"][0]
    removed = (portal["room_b_point"], portal["room_a_point"])
    damaged = replace(
        compiled.graph,
        connections=tuple(
            edge
            for edge in compiled.graph.connections
            if (edge.source, edge.target) != removed
        ),
    )
    validation = validate_authored_room_path_graph(damaged, tuple(rooms))
    assert not validation.ok
    assert any("no bidirectional PTH bridge" in issue for issue in validation.blocking_issues)


def test_sharply_concave_path_route_uses_shared_indexed_edge_midpoint() -> None:
    _install_payload_paths()
    from src.core.modules.authored_module_pathing import (
        AuthoredPathAnchor,
        AuthoredPathingRoom,
        compile_authored_pathing_for_rooms,
    )
    from src.core.modules.module_format import WOKData, WOKFace

    wok = WOKData(
        name="concave_pair",
        verts=[
            (7.3749, -2.8144, 0.0),
            (-6.3178, 0.0719, 0.0),
            (0.0, 0.0, 0.0),
            (-0.0901, 1.1697, 0.0),
        ],
        faces=[WOKFace(0, 3, 2, 1), WOKFace(1, 2, 3, 1)],
    )
    wok.rebuild_adjacencies()
    target = (
        sum(wok.verts[index][0] for index in (1, 2, 3)) / 3.0,
        sum(wok.verts[index][1] for index in (1, 2, 3)) / 3.0,
        0.0,
    )

    compiled = compile_authored_pathing_for_rooms(
        (AuthoredPathingRoom("concave", wok),),
        anchors=(AuthoredPathAnchor("target", target),),
    )

    assert compiled.validation.ok
    assert len(compiled.graph.points) >= 3
    assert any(point.metadata.get("source") == "gameplay_anchor" for point in compiled.graph.points)
