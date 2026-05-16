"""M16/T1603 VIS editor tests."""

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
    "ghostrigger_lyt_room_graph_for_vis_tests",
    _SRC_DIR / "core" / "lyt_room_graph.py",
)
ve = _load_module_direct(
    "ghostrigger_vis_editor_under_test",
    _SRC_DIR / "core" / "vis_editor.py",
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
class _Module:
    name: str = "vis_test"
    lyt: object = None
    vis: object = None
    room_woks: dict = field(default_factory=dict)


@dataclass
class _Hydrated:
    module_root: str = "vis_test"
    module: _Module = field(default_factory=_Module)


class _ModuleFormat:
    VISData = _VIS


def _install(monkeypatch):
    monkeypatch.setattr(ve, "_import_lyt_room_graph", lambda: lg)
    monkeypatch.setattr(ve, "_import_module_format", lambda: _ModuleFormat)


def _sample_module(with_vis=True):
    vis = _VIS({"room_a": ["room_b"], "room_b": ["room_a", "missing_room"]}) if with_vis else None
    return _Hydrated(
        module=_Module(
            lyt=_LYT([_Room("room_a"), _Room("room_b"), _Room("room_c")]),
            vis=vis,
        )
    )


def test_t1603_builds_editor_state_with_connections_and_warnings(monkeypatch):
    _install(monkeypatch)

    state = ve.build_vis_editor_state(_sample_module())

    assert state.ok is True
    assert state.code == "loaded"
    assert state.room_ids == ("room_a", "room_b", "room_c")
    assert state.visibility["room_a"] == ("room_b",)
    assert state.visibility["room_c"] == ()
    assert {issue.code for issue in state.issues} == {"VIS_TARGET_MISSING_ROOM"}
    edge = [connection for connection in state.connections if connection.source == "room_a"][0]
    assert edge.target == "room_b"
    assert edge.bidirectional is True


def test_t1603_preview_visibility_shows_one_hop_culling(monkeypatch):
    _install(monkeypatch)

    preview = ve.preview_visibility(_sample_module(), "room_a")

    assert preview.current_room == "room_a"
    assert preview.visible_rooms == ("room_a", "room_b")
    assert preview.hidden_rooms == ("room_c",)
    assert [connection.target for connection in preview.connections] == ["room_b"]


def test_t1603_add_and_remove_bidirectional_link(monkeypatch):
    _install(monkeypatch)
    module = _sample_module()

    added = ve.add_visibility_link(module, "room_a", "room_c", bidirectional=True)

    assert added.ok is True
    assert added.code == "link_added"
    assert "room_c" in module.module.vis.visibility["room_a"]
    assert "room_a" in module.module.vis.visibility["room_c"]
    assert added.preview.visible_rooms == ("room_a", "room_b", "room_c")

    removed = ve.remove_visibility_link(module, "room_a", "room_c", bidirectional=True)

    assert removed.ok is True
    assert "room_c" not in module.module.vis.visibility["room_a"]
    assert "room_a" not in module.module.vis.visibility["room_c"]


def test_t1603_creates_vis_when_missing(monkeypatch):
    _install(monkeypatch)
    module = _sample_module(with_vis=False)

    result = ve.add_visibility_link(module, "room_a", "room_b", bidirectional=False)

    assert result.ok is True
    assert isinstance(module.module.vis, _VIS)
    assert module.module.vis.visibility == {"room_a": ["room_b"], "room_b": [], "room_c": []}
    assert {issue.code for issue in result.state.issues} == set()


def test_t1603_make_full_visibility(monkeypatch):
    _install(monkeypatch)
    module = _sample_module(with_vis=False)

    result = ve.make_full_visibility(module)

    assert result.ok is True
    assert result.code == "full_visibility"
    assert module.module.vis.visibility == {
        "room_a": ["room_b", "room_c"],
        "room_b": ["room_a", "room_c"],
        "room_c": ["room_a", "room_b"],
    }


def test_t1603_create_vis_data_roundtrips_state(monkeypatch):
    _install(monkeypatch)
    state = ve.build_vis_editor_state(_sample_module())

    vis = ve.create_vis_data(state)

    assert isinstance(vis, _VIS)
    assert vis.visibility["room_a"] == ["room_b"]
    assert vis.visibility["room_b"] == ["room_a", "missing_room"]


def test_t1603_no_rooms_is_blocking_error(monkeypatch):
    _install(monkeypatch)
    module = _Hydrated(module=_Module(lyt=None, vis=_VIS({"ghost": ["other"]})))

    state = ve.build_vis_editor_state(module)

    assert state.ok is False
    assert state.code == "invalid"
    assert {issue.code for issue in state.issues} >= {"NO_ROOMS", "VIS_SOURCE_MISSING_ROOM"}
