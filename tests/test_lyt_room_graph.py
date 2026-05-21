"""M16/T1601 LYT room graph model tests."""

from __future__ import annotations

import importlib.util as _il_util
import pathlib
import sys
from dataclasses import dataclass, field


_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load_module_direct(name: str, path: pathlib.Path):
    spec = _il_util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:  # pragma: no cover
        raise ImportError(f"cannot create import spec for {path}")
    module = _il_util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


lg = _load_module_direct(
    "ghostrigger_lyt_room_graph_under_test",
    _SRC_DIR / "core" / "scene" / "lyt_room_graph.py",
)


@dataclass
class _Room:
    model: str
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class _DoorHook:
    name: str
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    qx: float = 0.0
    qy: float = 0.0
    qz: float = 0.0
    qw: float = 1.0


@dataclass
class _LYT:
    rooms: list[_Room] = field(default_factory=list)
    doorhooks: list[_DoorHook] = field(default_factory=list)


@dataclass
class _VIS:
    visibility: dict = field(default_factory=dict)


@dataclass
class _Module:
    name: str = "tar_m02aa"
    lyt: object = None
    vis: object = None
    room_woks: dict = field(default_factory=dict)


@dataclass
class _Hydrated:
    module_root: str = "tar_m02aa"
    module: _Module = field(default_factory=_Module)


class _ModuleFormat:
    LYTLayout = _LYT
    LYTRoom = _Room
    LYTDoorHook = _DoorHook


def _install(monkeypatch):
    monkeypatch.setattr(lg, "_import_module_format", lambda: _ModuleFormat)


def _sample_module():
    lyt = _LYT(
        rooms=[
            _Room("m02aa_01a", 0.0, 0.0, 0.0),
            _Room("m02aa_01b", 10.0, 0.0, 0.0),
            _Room("NULL", 20.0, 0.0, 0.0),
        ],
        doorhooks=[
            _DoorHook("door01", 9.0, 0.0, 0.0, 0.0, 0.0, 0.707, 0.707),
        ],
    )
    vis = _VIS({"m02aa_01a": ["m02aa_01b"], "m02aa_01b": ["m02aa_01a"]})
    return _Hydrated(module=_Module(lyt=lyt, vis=vis, room_woks={"m02aa_01a": object()}))


def test_t1601_builds_room_graph_with_transforms_visibility_and_hooks(monkeypatch):
    _install(monkeypatch)

    graph = lg.build_lyt_room_graph(_sample_module())

    assert graph.ok is True
    assert graph.code == "built"
    assert graph.module_root == "tar_m02aa"
    assert [room.room_id for room in graph.rooms] == ["m02aa_01a", "m02aa_01b"]
    assert graph.rooms[0].position == (0.0, 0.0, 0.0)
    assert graph.rooms[1].aurora_base_transform == (
        1.0, 0.0, 0.0, 10.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    )
    assert graph.rooms[0].visible_rooms == ("m02aa_01b",)
    assert graph.rooms[0].has_wok is True
    assert graph.rooms[1].has_wok is False
    assert graph.bounds_min == (0.0, 0.0, 0.0)
    assert graph.bounds_max == (10.0, 0.0, 0.0)
    assert graph.door_hooks[0].name == "door01"
    assert graph.door_hooks[0].nearest_room == "m02aa_01b"
    assert graph.door_hooks[0].rotation_quat == (0.0, 0.0, 0.707, 0.707)
    assert graph.visibility_edges[0].bidirectional is True
    assert {issue.code for issue in graph.issues} == {"SKIPPED_NULL_ROOM"}


def test_t1601_reports_missing_lyt_with_clear_error():
    graph = lg.build_lyt_room_graph(_Hydrated())

    assert graph.ok is False
    assert graph.code == "no_lyt"
    assert graph.issues[0].code == "NO_LYT"


def test_t1601_reports_duplicate_rooms_and_bad_vis_targets(monkeypatch):
    _install(monkeypatch)
    module = _Hydrated(
        module=_Module(
            lyt=_LYT([_Room("m12aa_01a"), _Room("m12aa_01a"), _Room("m12aa_01b")]),
            vis=_VIS({"m12aa_01a": ["missing_room"], "ghost_room": ["m12aa_01a"]}),
        )
    )

    graph = lg.build_lyt_room_graph(module)

    assert graph.ok is True
    codes = [issue.code for issue in graph.issues]
    assert "DUPLICATE_ROOM_MODEL" in codes
    assert "VIS_TARGET_MISSING_ROOM" in codes
    assert "VIS_SOURCE_MISSING_ROOM" in codes


def test_t1601_no_vis_is_info_not_blocking(monkeypatch):
    _install(monkeypatch)
    module = _Hydrated(
        module=_Module(
            lyt=_LYT([_Room("m01aa_01a"), _Room("m01aa_01b")]),
            vis=None,
        )
    )

    graph = lg.build_lyt_room_graph(module)

    assert graph.ok is True
    assert {issue.code for issue in graph.issues} == {"NO_VIS"}
    assert graph.visibility_edges == []


def test_t1601_create_layout_roundtrips_graph_nodes(monkeypatch):
    _install(monkeypatch)
    graph = lg.build_lyt_room_graph(_sample_module())

    layout = lg.create_lyt_layout(graph.rooms, graph.door_hooks)

    assert [room.model for room in layout.rooms] == ["m02aa_01a", "m02aa_01b"]
    assert layout.rooms[1].x == 10.0
    assert layout.doorhooks[0].name == "door01"
    assert layout.doorhooks[0].qz == 0.707


def test_t1601_add_and_move_room_mutates_loaded_lyt(monkeypatch):
    _install(monkeypatch)
    module = _Hydrated(module=_Module(lyt=_LYT([_Room("m01aa_01a")])))

    added = lg.add_room_to_lyt(module, "m01aa_01b", (5.0, 6.0, 0.0))
    moved = lg.move_room_in_lyt(module, "m01aa_01b", (8.0, 9.0, 1.0))

    assert added.ok is True
    assert added.code == "room_added"
    assert moved.ok is True
    assert moved.code == "room_moved"
    assert module.module.lyt.rooms[1].model == "m01aa_01b"
    assert (module.module.lyt.rooms[1].x, module.module.lyt.rooms[1].y, module.module.lyt.rooms[1].z) == (8.0, 9.0, 1.0)
    assert moved.room.aurora_base_transform[3] == 8.0


def test_t1601_move_missing_room_is_not_destructive(monkeypatch):
    _install(monkeypatch)
    module = _Hydrated(module=_Module(lyt=_LYT([_Room("m01aa_01a")])))

    result = lg.move_room_in_lyt(module, "missing", (1.0, 2.0, 3.0))

    assert result.ok is False
    assert result.code == "room_missing"
    assert len(module.module.lyt.rooms) == 1
