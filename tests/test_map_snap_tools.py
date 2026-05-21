"""M16/T1602 map snap/alignment tool tests."""

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
    "ghostrigger_lyt_room_graph_for_snap_tests",
    _SRC_DIR / "core" / "scene" / "lyt_room_graph.py",
)
snap = _load_module_direct(
    "ghostrigger_map_snap_tools_under_test",
    _SRC_DIR / "core" / "geometry" / "map_snap_tools.py",
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
class _GIT:
    _raw: dict = field(default_factory=dict)


@dataclass
class _Module:
    name: str = "map_test"
    lyt: object = None
    vis: object = None
    git: object = None
    room_woks: dict = field(default_factory=dict)


@dataclass
class _Hydrated:
    module_root: str = "map_test"
    module: _Module = field(default_factory=_Module)


class _ModuleFormat:
    LYTLayout = _LYT
    LYTRoom = _Room
    LYTDoorHook = _DoorHook


def _install(monkeypatch):
    monkeypatch.setattr(lg, "_import_module_format", lambda: _ModuleFormat)
    monkeypatch.setattr(snap, "_import_lyt_room_graph", lambda: lg)


def _sample_module():
    return _Hydrated(
        module=_Module(
            lyt=_LYT(
                rooms=[
                    _Room("room_a", 0.0, 0.0, 0.0),
                    _Room("room_b", 12.0, 0.0, 0.0),
                ],
                doorhooks=[
                    _DoorHook("a_exit", 5.0, 0.0, 0.0),
                    _DoorHook("b_exit", 8.0, 0.0, 0.0),
                ],
            ),
            vis=_VIS({"room_a": ["room_b"], "room_b": ["room_a"]}),
            git=_GIT(
                {
                    "Creature List": [
                        {"TemplateResRef": "npc", "XPosition": 0.2, "YPosition": 0.2, "ZPosition": 0.0}
                    ],
                    "Door List": [
                        {"TemplateResRef": "door", "X": 6.2, "Y": 0.4, "Z": 0.0}
                    ],
                    "Placeable List": [
                        {"TemplateResRef": "plc", "X": 11.8, "Y": 1.3, "Z": 0.0}
                    ],
                    "WaypointList": [
                        {"TemplateResRef": "wp", "XPosition": 4.8, "YPosition": 0.1, "ZPosition": 0.0}
                    ],
                }
            ),
        )
    )


def test_t1602_builds_room_and_door_snap_anchors(monkeypatch):
    _install(monkeypatch)
    graph = lg.build_lyt_room_graph(_sample_module())

    anchors = snap.build_snap_anchors(graph)

    ids = {anchor.anchor_id for anchor in anchors}
    assert "room:room_a:origin" in ids
    assert "room:room_b:origin" in ids
    door_a = [anchor for anchor in anchors if anchor.name == "a_exit"][0]
    door_b = [anchor for anchor in anchors if anchor.name == "b_exit"][0]
    assert door_a.kind == "doorhook"
    assert door_a.room_id == "room_a"
    assert door_a.local_position == (5.0, 0.0, 0.0)
    assert door_b.room_id == "room_b"
    assert door_b.local_position == (-4.0, 0.0, 0.0)


def test_t1602_finds_and_snaps_room_to_nearest_doorhook(monkeypatch):
    _install(monkeypatch)
    module = _sample_module()

    result = snap.snap_room_to_nearest_anchor(module, "room_b", max_distance=4.0)

    assert result.ok is True
    assert result.code == "room_snapped"
    assert result.old_position == (12.0, 0.0, 0.0)
    assert result.new_position == (9.0, 0.0, 0.0)
    assert result.delta == (-3.0, 0.0, 0.0)
    assert module.module.lyt.rooms[1].x == 9.0
    assert result.candidate.target_anchor.room_id == "room_a"


def test_t1602_snaps_room_to_grid(monkeypatch):
    _install(monkeypatch)
    module = _sample_module()
    module.module.lyt.rooms[1].x = 12.4
    module.module.lyt.rooms[1].y = 9.6
    module.module.lyt.rooms[1].z = 2.4

    result = snap.snap_room_to_grid(module, "room_b", grid_size=5.0, axes=("x", "y"))

    assert result.ok is True
    assert result.code == "room_grid_snapped"
    assert result.old_position == (12.4, 9.6, 2.4)
    assert result.new_position == (10.0, 10.0, 2.4)
    assert (module.module.lyt.rooms[1].x, module.module.lyt.rooms[1].y, module.module.lyt.rooms[1].z) == (10.0, 10.0, 2.4)


def test_t1602_aligns_creatures_doors_placeables_and_waypoints_to_room(monkeypatch):
    _install(monkeypatch)
    module = _sample_module()

    creature = snap.align_object_to_room(module, "creature", 0, room_id="room_a", offset=(1.0, 2.0, 0.0))
    door = snap.align_object_to_room(module, "door", 0, room_id="room_b", offset=(0.5, 0.0, 0.0))
    placeable = snap.align_object_to_room(module, "placeable", 0, room_id="room_b", offset=(1.1, 1.1, 0.0), grid_size=1.0)
    waypoint = snap.align_object_to_room(module, "waypoint", 0, room_id="room_a", offset=(0.2, 0.2, 0.0), grid_size=0.5)

    raw = module.module.git._raw
    assert creature.ok is True
    assert raw["Creature List"][0]["XPosition"] == 1.0
    assert raw["Creature List"][0]["YPosition"] == 2.0
    assert door.ok is True
    assert raw["Door List"][0]["X"] == 12.5
    assert raw["Door List"][0]["Y"] == 0.0
    assert placeable.ok is True
    assert raw["Placeable List"][0]["X"] == 13.0
    assert raw["Placeable List"][0]["Y"] == 1.0
    assert waypoint.ok is True
    assert raw["WaypointList"][0]["XPosition"] == 0.0
    assert raw["WaypointList"][0]["YPosition"] == 0.0


def test_t1602_snaps_object_to_grid_and_reports_nearest_room(monkeypatch):
    _install(monkeypatch)
    module = _sample_module()

    result = snap.snap_object_to_grid(module, "placeable", 0, grid_size=1.0)

    assert result.ok is True
    assert result.code == "object_grid_snapped"
    assert result.old_position == (11.8, 1.3, 0.0)
    assert result.new_position == (12.0, 1.0, 0.0)
    assert result.room_id == "room_b"
    assert module.module.git._raw["Placeable List"][0]["X"] == 12.0


def test_t1602_reports_missing_room_anchor_and_object(monkeypatch):
    _install(monkeypatch)
    module = _sample_module()

    room = snap.snap_room_to_grid(module, "missing_room", grid_size=5.0)
    obj = snap.align_object_to_room(module, "creature", 5, room_id="room_a")
    anchors = snap.snap_room_to_anchor(module, "room_a", "missing", "also_missing")

    assert room.ok is False
    assert room.code == "room_missing"
    assert obj.ok is False
    assert obj.code == "object_missing"
    assert anchors.ok is False
    assert anchors.code == "anchor_missing"
