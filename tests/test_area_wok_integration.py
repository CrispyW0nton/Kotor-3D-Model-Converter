"""M16/T1604 area WOK integration tests."""

from __future__ import annotations

import importlib.util as _il_util
import pathlib
import sys
from dataclasses import dataclass, field


_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SCENE_PAYLOAD = _REPO_ROOT / "native" / "GhostRigger.Domain.Core.Scene" / "Python"
_MODULES_PAYLOAD = _REPO_ROOT / "native" / "GhostRigger.Domain.Core.Modules" / "Python"
for _payload in (_SCENE_PAYLOAD, _MODULES_PAYLOAD):
    if str(_payload) not in sys.path:
        sys.path.insert(0, str(_payload))
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
    "ghostrigger_lyt_room_graph_for_wok_tests",
    _SCENE_PAYLOAD / "src" / "core" / "scene" / "lyt_room_graph.py",
)
awi = _load_module_direct(
    "ghostrigger_area_wok_integration_under_test",
    _MODULES_PAYLOAD / "src" / "core" / "modules" / "area_wok_integration.py",
)


@dataclass
class _Room:
    model: str
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class _LYT:
    rooms: list[_Room] = field(default_factory=list)
    doorhooks: list = field(default_factory=list)


@dataclass
class _VIS:
    visibility: dict = field(default_factory=dict)


@dataclass
class _Face:
    v1: int
    v2: int
    v3: int
    surface: int
    adj1: int = -1
    adj2: int = -1
    adj3: int = -1


@dataclass
class _Wok:
    verts: list[tuple[float, float, float]] = field(default_factory=list)
    faces: list[_Face] = field(default_factory=list)

    def walkable_face_count(self):
        return sum(1 for face in self.faces if face.surface in _WalkmeshEditor.WALKABLE_IDS)

    def non_walk_face_count(self):
        return sum(1 for face in self.faces if face.surface == 7)

    def boundary_edges(self):
        edges = []
        for face_index, face in enumerate(self.faces):
            if face.surface not in _WalkmeshEditor.WALKABLE_IDS:
                continue
            verts = (face.v1, face.v2, face.v3)
            for edge_index, adjacent in enumerate((face.adj1, face.adj2, face.adj3)):
                if adjacent == -1 or self.faces[adjacent].surface not in _WalkmeshEditor.WALKABLE_IDS:
                    edges.append((verts[edge_index], verts[(edge_index + 1) % 3], face_index, edge_index))
        return edges


@dataclass
class _Module:
    name: str = "wok_area"
    lyt: object = None
    vis: object = None
    room_woks: dict = field(default_factory=dict)


@dataclass
class _Hydrated:
    module_root: str = "wok_area"
    module: _Module = field(default_factory=_Module)


class _WalkmeshEditor:
    WOK_SURFACE_NAMES = {
        1: "DIRT",
        4: "STONE",
        7: "NON_WALK",
        18: "DOOR",
    }
    WALKABLE_IDS = {1, 4, 18}

    @staticmethod
    def _surface_names():
        return dict(_WalkmeshEditor.WOK_SURFACE_NAMES)

    @staticmethod
    def _walkable_ids():
        return set(_WalkmeshEditor.WALKABLE_IDS)


def _install(monkeypatch):
    monkeypatch.setattr(awi, "_import_lyt_room_graph", lambda: lg)
    monkeypatch.setattr(awi, "_import_walkmesh_editor", lambda: _WalkmeshEditor)


def _room_wok(offset_x=0.0, *, bad=False):
    if bad:
        return _Wok(
            verts=[
                (0.0, 0.0, 0.0),
                (1.0, 0.0, 0.0),
                (0.0, 1.0, 0.0),
                (0.0, 0.0, 0.0),
            ],
            faces=[
                _Face(0, 2, 1, 1),      # negative XY winding
                _Face(0, 3, 3, 99),     # degenerate + invalid material
            ],
        )
    return _Wok(
        verts=[
            (0.0 + offset_x, 0.0, 0.0),
            (1.0 + offset_x, 0.0, 0.0),
            (0.0 + offset_x, 1.0, 0.0),
            (1.0 + offset_x, 1.0, 0.0),
        ],
        faces=[
            _Face(0, 1, 2, 1, -1, 1, -1),
            _Face(1, 3, 2, 18, -1, -1, 0),
        ],
    )


def _sample_module(*, gap=False, missing=False, bad=False):
    room_b_x = 1.0 if not gap else 10.0
    lyt = _LYT([_Room("room_a", 0.0, 0.0, 0.0), _Room("room_b", room_b_x, 0.0, 0.0)])
    vis = _VIS({"room_a": ["room_b"], "room_b": ["room_a"]})
    woks = {"room_a": _room_wok(), "room_b": _room_wok()}
    if missing:
        woks.pop("room_b")
    if bad:
        woks["room_a"] = _room_wok(bad=True)
    return _Hydrated(module=_Module(lyt=lyt, vis=vis, room_woks=woks))


def test_t1604_summarizes_room_woks_and_world_bounds(monkeypatch):
    _install(monkeypatch)

    report = awi.validate_area_woks(_sample_module())

    assert report.ok is True
    assert report.code == "valid"
    assert len(report.rooms) == 2
    room_a = report.rooms[0]
    room_b = report.rooms[1]
    assert room_a.vertex_count == 4
    assert room_a.face_count == 2
    assert room_a.walkable_face_count == 2
    assert room_a.perimeter_edge_count >= 1
    assert room_a.transition_face_count == 1
    assert room_a.bounds_min == (0.0, 0.0, 0.0)
    assert room_a.bounds_max == (1.0, 1.0, 0.0)
    assert room_b.bounds_min == (1.0, 0.0, 0.0)
    assert report.walkable_face_count == 4
    assert report.transition_face_count == 2
    assert report.seams[0].ok is True
    assert report.seams[0].code == "seam_ok"
    assert len(report.overlays) == 2
    overlay = report.overlays[0]
    assert overlay.room_id == "room_a"
    assert len(overlay.faces) == 2
    assert len(overlay.edges) == 4
    assert overlay.faces[0].surface_name == "DIRT"
    assert overlay.faces[0].walkable is True
    assert overlay.faces[0].issue_codes == ()
    assert {edge.kind for edge in overlay.edges} == {"boundary"}
    assert {edge.issue_codes for edge in overlay.edges} == {("BOUNDARY_EDGE",)}


def test_t1604_flags_missing_room_wok_as_blocking(monkeypatch):
    _install(monkeypatch)

    report = awi.validate_area_woks(_sample_module(missing=True))

    assert report.ok is False
    assert report.code == "invalid"
    assert {issue.code for issue in report.issues} >= {"ROOM_WOK_MISSING", "MISSING_WOK"}
    missing = [summary for summary in report.rooms if summary.room_id == "room_b"][0]
    assert missing.has_wok is False


def test_t1604_flags_invalid_material_reversed_and_degenerate_faces(monkeypatch):
    _install(monkeypatch)

    report = awi.validate_area_woks(_sample_module(bad=True))

    codes = {issue.code for issue in report.issues}
    assert "INVALID_WOK_MATERIAL" in codes
    assert "REVERSED_FACE_WINDING" in codes
    assert "DEGENERATE_FACE" in codes
    room_a = [summary for summary in report.rooms if summary.room_id == "room_a"][0]
    assert room_a.invalid_material_faces == (1,)
    assert room_a.reversed_faces == (0,)
    assert room_a.degenerate_faces == (1,)
    overlay = [item for item in report.overlays if item.room_id == "room_a"][0]
    assert overlay.faces[0].issue_codes == ("REVERSED_FACE_WINDING",)
    assert overlay.faces[1].issue_codes == ("INVALID_WOK_MATERIAL", "DEGENERATE_FACE")
    assert overlay.faces[1].walkable is False


def test_t2638_wok_overlay_marks_edges_against_non_walk_faces_as_blocked(monkeypatch):
    _install(monkeypatch)
    lyt = _LYT([_Room("room_a", 0.0, 0.0, 0.0)])
    vis = _VIS({"room_a": []})
    module = _Hydrated(
        module=_Module(
            lyt=lyt,
            vis=vis,
            room_woks={
                "room_a": _Wok(
                    verts=[
                        (0.0, 0.0, 0.0),
                        (1.0, 0.0, 0.0),
                        (0.0, 1.0, 0.0),
                        (1.0, 1.0, 0.0),
                    ],
                    faces=[
                        _Face(0, 1, 2, 1, -1, 1, -1),
                        _Face(1, 3, 2, 7),
                    ],
                )
            },
        )
    )

    report = awi.validate_area_woks(module)

    overlay = report.overlays[0]
    blocked_edges = [edge for edge in overlay.edges if edge.kind == "blocked"]
    assert len(blocked_edges) == 1
    assert blocked_edges[0].face_index == 0
    assert blocked_edges[0].edge_index == 1
    assert blocked_edges[0].issue_codes == ("BLOCKED_EDGE",)
    assert overlay.faces[1].surface_name == "NON_WALK"
    assert overlay.faces[1].walkable is False


def test_t2704_vertical_non_walk_boundary_walls_are_not_degenerate(monkeypatch):
    _install(monkeypatch)
    lyt = _LYT([_Room("room_a", 0.0, 0.0, 0.0)])
    vis = _VIS({"room_a": []})
    module = _Hydrated(
        module=_Module(
            lyt=lyt,
            vis=vis,
            room_woks={
                "room_a": _Wok(
                    verts=[
                        (0.0, 0.0, 0.0),
                        (1.0, 0.0, 0.0),
                        (0.0, 1.0, 0.0),
                        (1.0, 0.0, 2.0),
                    ],
                    faces=[
                        _Face(0, 1, 2, 1),
                        _Face(0, 1, 3, 7),
                    ],
                )
            },
        )
    )

    report = awi.validate_area_woks(module)

    assert "DEGENERATE_FACE" not in {issue.code for issue in report.issues}
    room = report.rooms[0]
    assert room.face_count == 2
    assert room.walkable_face_count == 1
    assert room.non_walk_face_count == 1
    assert room.degenerate_faces == ()
    overlay = report.overlays[0]
    assert overlay.faces[1].surface_name == "NON_WALK"
    assert overlay.faces[1].issue_codes == ()


def test_t1604_flags_seam_gap_between_connected_rooms(monkeypatch):
    _install(monkeypatch)

    report = awi.validate_area_woks(_sample_module(gap=True), seam_tolerance=0.25)

    assert report.ok is True
    seam = report.seams[0]
    assert seam.ok is False
    assert seam.code == "seam_gap"
    assert seam.min_boundary_distance > 0.25
    assert "WOK_SEAM_GAP" in {issue.code for issue in report.issues}


def test_t1604_no_rooms_reports_clear_error(monkeypatch):
    _install(monkeypatch)
    module = _Hydrated(module=_Module(lyt=None, vis=None, room_woks={}))

    report = awi.validate_area_woks(module)

    assert report.ok is False
    assert report.code == "no_rooms"
    assert report.issues[0].code == "NO_ROOMS"
