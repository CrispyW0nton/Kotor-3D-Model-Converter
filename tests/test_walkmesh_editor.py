"""M15/T1503 walkmesh editor framework tests."""

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


we = _load_module_direct(
    "ghostrigger_walkmesh_editor_under_test",
    _SRC_DIR / "core" / "walkmesh_editor.py",
)


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
    name: str = "m02aa_01a"
    verts: list[tuple[float, float, float]] = field(default_factory=list)
    faces: list[_Face] = field(default_factory=list)
    raw: bytes = b""

    def walkable_face_count(self):
        return sum(1 for face in self.faces if face.surface in _ModuleFormat.WALKABLE_IDS)

    def non_walk_face_count(self):
        return sum(1 for face in self.faces if face.surface == 7)

    def boundary_edges(self):
        edges = []
        for face_index, face in enumerate(self.faces):
            if face.surface not in _ModuleFormat.WALKABLE_IDS:
                continue
            for edge_index, adjacent in enumerate((face.adj1, face.adj2, face.adj3)):
                if adjacent == -1 or self.faces[adjacent].surface not in _ModuleFormat.WALKABLE_IDS:
                    verts = (face.v1, face.v2, face.v3)
                    edges.append((verts[edge_index], verts[(edge_index + 1) % 3], face_index, edge_index))
        return edges

    def set_face_surface(self, face_idx, surface_id):
        if face_idx < 0 or face_idx >= len(self.faces):
            return False
        self.faces[face_idx].surface = surface_id
        return True

    def surface_distribution(self):
        dist = {}
        for face in self.faces:
            dist[face.surface] = dist.get(face.surface, 0) + 1
        return dist

    def face_at_point(self, px, py):
        for face_index, face in enumerate(self.faces):
            try:
                ax, ay = self.verts[face.v1][0], self.verts[face.v1][1]
                bx, by = self.verts[face.v2][0], self.verts[face.v2][1]
                cx, cy = self.verts[face.v3][0], self.verts[face.v3][1]
            except IndexError:
                continue

            def _sign(x1, y1, x2, y2, x3, y3):
                return (x1 - x3) * (y2 - y3) - (x2 - x3) * (y1 - y3)

            d1 = _sign(px, py, ax, ay, bx, by)
            d2 = _sign(px, py, bx, by, cx, cy)
            d3 = _sign(px, py, cx, cy, ax, ay)
            if not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0)):
                return face_index
        return -1

    def to_bytes(self):
        surfaces = ",".join(str(face.surface) for face in self.faces)
        return f"verts={len(self.verts)};faces={len(self.faces)};surfaces={surfaces}".encode("ascii")

    @classmethod
    def from_bytes(cls, data):
        text = data.decode("ascii")
        parts = dict(chunk.split("=", 1) for chunk in text.split(";") if "=" in chunk)
        vertex_count = int(parts["verts"])
        surfaces = [int(value) for value in parts.get("surfaces", "").split(",") if value]
        return cls(
            name="roundtrip",
            verts=[(float(i), 0.0, 0.0) for i in range(vertex_count)],
            faces=[_Face(0, 1, 2, surface) for surface in surfaces],
            raw=data,
        )


class _ModuleFormat:
    WOK_SURFACE_NAMES = {
        0: "INVALID",
        1: "DIRT",
        4: "STONE",
        7: "NON_WALK",
        18: "DOOR",
    }
    WALKABLE_IDS = {1, 4, 18}
    WOKData = _Wok


class _Renderer:
    @staticmethod
    def surface_color(surface_id):
        return (float(surface_id) / 20.0, 0.5, 0.25, 0.75)


@dataclass
class _Module:
    name: str = "tar_m02aa"
    room_woks: dict = field(default_factory=dict)
    wok: object = None


def _install(monkeypatch):
    monkeypatch.setattr(we, "_import_module_format", lambda: _ModuleFormat)
    monkeypatch.setattr(we, "_import_walkmesh_renderer", lambda: _Renderer)


def _sample_wok():
    return _Wok(
        verts=[
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (1.0, 1.0, 0.0),
        ],
        faces=[
            _Face(0, 1, 2, 1, -1, 1, -1),
            _Face(1, 3, 2, 7, -1, -1, 0),
            _Face(1, 3, 2, 18, -1, -1, -1),
        ],
        raw=b"original",
    )


def _module_with_wok(wok=None):
    return _Module(room_woks={"m02aa_01a": wok or _sample_wok()})


def test_t1503_builds_workbench_with_faces_palette_and_validation(monkeypatch):
    _install(monkeypatch)

    result = we.build_walkmesh_workbench(_module_with_wok(), room="m02aa_01a")

    assert result.ok is True
    assert result.code == "loaded"
    assert result.room == "m02aa_01a"
    assert len(result.faces) == 3
    assert result.faces[0].surface_name == "DIRT"
    assert result.faces[0].walkable is True
    assert result.faces[1].surface_name == "NON_WALK"
    assert result.faces[1].walkable is False
    assert result.faces[0].centroid == (1.0 / 3.0, 1.0 / 3.0, 0.0)
    assert {surface.surface_id for surface in result.surfaces} == {0, 1, 4, 7, 18}
    assert result.validation.ok is True
    assert result.validation.walkable_face_count == 2
    assert result.validation.non_walk_face_count == 1
    assert result.validation.boundary_edge_count >= 1
    assert result.validation.transition_face_count == 1


def test_t1503_selects_walkmesh_face_by_point_and_index(monkeypatch):
    _install(monkeypatch)
    module = _module_with_wok()

    by_point = we.select_walkmesh_face(module, room="m02aa_01a", x=0.2, y=0.2)
    by_index = we.select_walkmesh_face(module, room="m02aa_01a", face_index=1)

    assert by_point.ok is True
    assert by_point.face_index == 0
    assert by_point.face.selected is True
    assert by_point.workbench.selected_face_index == 0
    assert by_index.ok is True
    assert by_index.face.surface_name == "NON_WALK"


def test_t1503_edits_face_surface_and_paints_point(monkeypatch):
    _install(monkeypatch)
    module = _module_with_wok()

    edited = we.set_walkmesh_face_surface(module, [0, 1], 4, room="m02aa_01a")
    painted = we.paint_walkmesh_point(module, x=0.2, y=0.2, surface_id=18, room="m02aa_01a")

    assert edited.ok is True
    assert edited.code == "surface_changed"
    assert edited.old_surfaces == {0: 1, 1: 7}
    assert module.room_woks["m02aa_01a"].faces[0].surface == 18
    assert module.room_woks["m02aa_01a"].faces[1].surface == 4
    assert painted.ok is True
    assert painted.new_surface_name == "DOOR"
    assert painted.workbench.selected_face_index == 0


def test_t1503_rejects_unknown_surface_and_missing_face(monkeypatch):
    _install(monkeypatch)
    module = _module_with_wok()

    unknown = we.set_walkmesh_face_surface(module, 0, 99, room="m02aa_01a")
    missing = we.select_walkmesh_face(module, room="m02aa_01a", face_index=30)

    assert unknown.ok is False
    assert unknown.code == "unknown_surface"
    assert module.room_woks["m02aa_01a"].faces[0].surface == 1
    assert missing.ok is False
    assert missing.code == "face_not_found"


def test_t1503_validation_reports_bad_indices_unknown_surfaces_and_empty_wok(monkeypatch):
    _install(monkeypatch)
    bad = _Wok(
        verts=[(0.0, 0.0, 0.0)],
        faces=[_Face(0, 9, 2, 99, 5, -1, -1)],
    )
    empty = _Wok()

    bad_report = we.validate_walkmesh(_module_with_wok(bad), room="m02aa_01a")
    empty_report = we.validate_walkmesh(_module_with_wok(empty), room="m02aa_01a")

    assert bad_report.ok is False
    assert {issue.code for issue in bad_report.issues} >= {"BAD_VERTEX_INDEX", "UNKNOWN_SURFACE", "BAD_ADJACENCY"}
    assert empty_report.ok is False
    assert {issue.code for issue in empty_report.issues} >= {"NO_VERTICES", "NO_FACES"}


def test_t1503_roundtrip_preserves_counts_and_surface_distribution(monkeypatch):
    _install(monkeypatch)
    module = _module_with_wok()

    result = we.roundtrip_walkmesh(module, room="m02aa_01a")

    assert result.ok is True
    assert result.code == "roundtrip_ok"
    assert result.original_size == len(b"original")
    assert result.output_size > 0
    assert result.reparsed_vertex_count == 4
    assert result.reparsed_face_count == 3
    assert result.material_distribution == {1: 1, 7: 1, 18: 1}


def test_t1503_missing_walkmesh_reports_clear_error(monkeypatch):
    _install(monkeypatch)

    workbench = we.build_walkmesh_workbench(_Module(), room="missing")
    report = we.validate_walkmesh(_Module(), room="missing")

    assert workbench.ok is False
    assert workbench.code == "no_walkmesh"
    assert report.ok is False
    assert report.code == "no_walkmesh"
    assert report.issues[0].code == "NO_WALKMESH"
